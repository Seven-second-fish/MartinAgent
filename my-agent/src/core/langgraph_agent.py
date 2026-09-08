"""
LangGraph 搜索智能体：理解 → 搜索 → 回答，线性状态机 + 跨轮次记忆。

编排模型（LangGraph 的核心概念）：
- 所有节点共享一份 state（见 SearchState），节点之间不直接传参；
- 每个节点读取自己需要的字段，返回一个"部分更新"dict，框架把它合并回 state
  后再交给下一个节点——这就是节点间传递数据的方式；
- messages 字段带有 add_messages reducer（Annotated[list, add_messages]），
  节点返回的消息是"追加"而不是"覆盖"，因此多轮历史得以保留；
- compile(checkpointer) 之后，同一 thread_id 的多次 invoke 共享同一份 state，
  这是多轮对话记忆的基础（图只需构建一次，不用每轮重建）。

对外接口：run(task) -> str / reset()，与 main.py 的 Agent Protocol 一致。
"""

from __future__ import annotations

import json
import re
from typing import Annotated, TypedDict

from colorama import Fore, Style
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from src.core.llm_client import LLMClient
from src.tools import call_tool

load_dotenv()


class SearchState(TypedDict):
    # 跨轮次共享的历史消息；带 reducer 注解，节点返回时追加而非覆盖
    messages: Annotated[list, add_messages]
    user_summary: str    # 本轮：LLM 结合历史对用户需求的总结（仅作补充，原话以 messages 末条为准）
    search_query: str    # 本轮：提炼出的搜索关键词
    search_results: str  # 本轮：搜索工具返回的文本
    final_answer: str    # 本轮：最终答案
    step: str            # 本轮流程标记：understood / searched / search_failed / completed


# 工具契约：出错不抛异常，而是返回以这些前缀开头的文本（见 src/tools/__init__.py）
_TOOL_ERROR_PREFIXES = ("错误", "搜索失败", "搜索请求失败", "搜索响应解析失败", "工具执行异常")
_WEBSEARCH_TOOL = "websearch_tool"   # src/tools/search.py 中注册的工具名
_HISTORY_LIMIT = 6    # 生成答案时参考的最近消息条数
_HISTORY_CUT = 300    # 单条历史消息截断长度


class LangGraphAgent:
    """一个"先查资料、再给答案"的多轮搜索智能体。"""

    def __init__(self) -> None:
        self.llm_client = LLMClient()
        # 会话 = 一个 checkpointer + 一个 thread_id；reset() 会整组换新
        self._thread_id = 1
        self._memory = InMemorySaver()
        self._app = self._build_search_assistant()

    # ---------------------------------------------------------------- 图构建

    def _build_search_assistant(self):
        """把三个节点串成线性图并编译。

        注意：add_node/add_edge/compile 只做登记与结构校验，节点函数要到
        app.invoke(...) 那一刻才会真正执行。
        """
        workflow = StateGraph(SearchState)

        workflow.add_node("understand", self._understand_node)
        workflow.add_node("search", self._search_node)
        workflow.add_node("answer", self._answer_node)

        workflow.add_edge(START, "understand")
        workflow.add_edge("understand", "search")
        workflow.add_edge("search", "answer")
        workflow.add_edge("answer", END)

        # #设置入口点
        # workflow.set_entry_point("input_preferences")
        # #添加边（主要流程）
        # workflow.add_edge("input_preferences", "recommend_destinations")
        # workflow.add_edge("recommend_destinations", "calculate_budget")
        # workflow.add_edge("calculate_budget", "check_budget") # 进入判断节点

        # 重新计算后再次检查预算
        # workflow.add_conditional_edges()

        return workflow.compile(checkpointer=self._memory)

    # ------------------------------------------------------------- 节点函数
    # 每个节点签名固定：node(state) -> dict。state 是整个共享状态；
    # 返回的 dict 只写本轮新产生的字段，没写的字段保持原值。

    def _understand_node(self, state: SearchState) -> dict:
        """步骤1：结合历史把当前问题提炼为「需求总结 + 搜索词」。

        新输入由 run() 以 HumanMessage 追加，本轮问题一定在 messages 末尾
        （不要用 index 0，多轮之后那里是旧历史）。

        提炼必须带历史：追问「那它呢？」这类指代句，离开上文根本无法转成
        可搜索的关键词——指代消解（query rewriting）是搜索型 agent
        支持多轮对话的关键一步。
        """
        question = state["messages"][-1].content
        history = self._format_history(state)  # 本轮问题之前的历史；无则返回"（无）"

        understand_prompt = (
            f"你是搜索词提炼器。用户的当前问题可能是对上文的追问，"
            f"你需要结合最近对话理解真实意图，并把问题改写成可直接搜索的形式。\n\n"
            f"最近对话：\n{history}\n\n"
            f'用户当前问题："{question}"\n\n'
            "只输出一个 JSON 对象，不要输出任何其他内容：\n"
            '{"summary": "用户现在想了解什么（含必要的上文信息，一句话）", '
            '"search_query": "自足的搜索关键词（指代已消解，不含它/那个/这种等代词）"}'
        )
        # 理解结果是给解析器用的 JSON 契约，不是给人看的正文——若用
        # chat_stream，裸 JSON 会实时流到屏幕（是噪音而非进度）。这里用
        # 静默 chat()；它产出的搜索词随后由 🔍 行打印，那就是进度反馈。
        result = self.llm_client.chat([{"role": "user", "content": understand_prompt}])

        summary, search_query = self._parse_understand_response(result.content, question)
        return {
            "user_summary": summary,
            "search_query": search_query,
            "step": "understood",
        }

    def _search_node(self, state: SearchState) -> dict:
        """步骤2：用提炼出的关键词调用项目内的 websearch 工具。"""
        search_query = state["search_query"]
        print(f"\n{Fore.YELLOW}🔍 正在搜索: {search_query}{Style.RESET_ALL}")

        search_results = call_tool(_WEBSEARCH_TOOL, {"query": search_query})
        # 工具失败返回错误文本（不抛异常）→ 标记 failed，让 answer 节点走知识回退
        if search_results.startswith(_TOOL_ERROR_PREFIXES):
            return {"search_results": search_results, "step": "search_failed"}
        return {"search_results": search_results, "step": "searched"}

    def _answer_node(self, state: SearchState) -> dict:
        """步骤3：基于搜索结果（或知识回退）生成最终答案，并写入历史。

        正文用 chat_stream：答案实时流式打印给用户（看得见的执行过程），
        run() 不再重复打印，返回值仅作为 run() 的返回/历史记录。
        """
        question = state["messages"][-1].content

        if state["step"] == "search_failed":
            answer_prompt = (
                "搜索服务暂时不可用（原因：" + state["search_results"] + "）。\n"
                "请基于你自己的知识回答用户的问题，并明确告知未能联网核实：\n" + question
            )
        else:
            answer_prompt = (
                "你是信息检索助手。请综合下面的搜索结果回答用户，"
                "答案要准确、结构清晰；资料不足时如实说明，不要编造。\n\n"
                f"用户问题：{question}\n\n"
                f"用户补充（搜索前的理解，供参考）：{state['user_summary']}\n\n"
                f"搜索结果：\n{state['search_results']}\n\n"
                f"最近对话（供衔接上下文，如与本问题无关可忽略）：\n"
                f"{self._format_history(state)}"
            )

        result = self.llm_client.chat_stream([{"role": "user", "content": answer_prompt}])

        return {
            "final_answer": result.content,
            "step": "completed",
            # 只有最终答案进历史；"我将为您搜索…"这类过程消息不进历史，避免污染多轮上下文
            "messages": [AIMessage(content=result.content)],
        }

    # ------------------------------------------------------------------ 对外

    def run(self, task: str) -> str:
        """执行一轮：把任务追加进会话历史，驱动 理解→搜索→回答 整条流水线。"""
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"🤖 多智能体任务开始：{task}")
        print(f"{'=' * 60}{Style.RESET_ALL}")

        # 本轮输入 = 追加一条 HumanMessage；checkpointer 负责把它并入该会话已有历史
        result = self._app.invoke(
            {"messages": [HumanMessage(content=task)]},
            {"configurable": {"thread_id": str(self._thread_id)}},
        )

        answer = result["final_answer"]
        # 答案已由 answer 节点里的 chat_stream 实时逐字打出，这里只画收尾线，
        # 不再重复打印整段内容（避免同一答案出现两遍）
        print(f"\n{Fore.GREEN}{'─' * 60}{Style.RESET_ALL}")
        return answer

    def reset(self) -> None:
        """开启新会话：换掉 checkpointer 与 thread_id，旧会话记忆随之丢弃。

        InMemorySaver 没有清空接口，所以"清空"= 重建 saver 并重新编译图
        （编译很轻量；图结构不变，只是绑定新的记忆存储）。
        """
        self._thread_id += 1
        self._memory = InMemorySaver()
        self._app = self._build_search_assistant()
        print("🧹 会话已重置，历史记忆已清空")

    # ------------------------------------------------------------- 辅助方法

    @staticmethod
    def _parse_understand_response(text: str, fallback: str) -> tuple[str, str]:
        """从 LLM 输出里稳健提取 summary / search_query。

        要求模型输出纯 JSON，但实际输出可能带 ```json 代码块、前后缀文字等，
        这里先抓取第一个花括号块再解析；任何失败都回退用原话，保证不崩。
        """
        try:
            match = re.search(r"\{.*\}", text, re.S)
            data = json.loads(match.group(0) if match else text)
            summary = str(data.get("summary") or fallback).strip()
            search_query = str(data.get("search_query") or fallback).strip()
            return summary, search_query
        except (json.JSONDecodeError, AttributeError, TypeError):
            return fallback, fallback

    @staticmethod
    def _format_history(state: SearchState) -> str:
        """把当前问题之前的最近几轮对话压成紧凑文本，供 answer 衔接上下文。"""
        previous = state["messages"][:-1]  # 末条是本轮问题，历史取它之前的部分
        if not previous:
            return "（无）"

        lines = []
        for msg in previous[-_HISTORY_LIMIT:]:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = str(msg.content or "")[:_HISTORY_CUT].replace("\n", " ")
            lines.append(f"{role}：{content}")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    agent = LangGraphAgent()
    task = " ".join(sys.argv[1:]) or input("请输入任务：")
    agent.run(task)
