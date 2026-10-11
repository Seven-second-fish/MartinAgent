"""五种 Agent 主循环的行为测试（全部 mock LLM，不发真实网络请求）。

覆盖：
  1. ReActAgent：多轮「工具调用 → 观察写回 → 最终答案」，校验消息协议
  2. Planner：submit_plan 函数调用契约（工具优先、正文 JSON 兜底）
  3. PlanAndSolveAgent：规划 → 逐步执行，返回最后一步答案
  4. ReflectionAgent：执行 → 反思 → 优化，直到 needs_improvement=false 收敛
  5. AutoGenAgent：多角色共享历史轮流发言，遇 TERMINATE 结束

LLMClient 构造时会读 OPENAI_API_KEY，这里在导入前塞占位值；
所有用例都把 agent 的 llm_client 换成 FakeLLMClient，不会发出任何真实请求。
"""

from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from martin_agent.core.autogen_agent import AutoGenAgent  # noqa: E402
from martin_agent.core.langgraph_agent import LangGraphAgent  # noqa: E402
from martin_agent.core.llm_client import ChatResult, ToolCall  # noqa: E402
from martin_agent.core.plan_solve_agent import PlanAndSolveAgent, Planner  # noqa: E402
from martin_agent.core.react_agent import ReActAgent  # noqa: E402
from martin_agent.core.reflection_agent import ReflectionAgent  # noqa: E402


class FakeLLMClient:
    """按顺序吐出预设 ChatResult 的假客户端，并记录收到的消息。"""

    def __init__(self, results: list[ChatResult]) -> None:
        self._queue = list(results)
        self.calls: list[list[dict]] = []

    def chat_stream(self, messages, tools=None) -> ChatResult:  # noqa: ARG002
        self.calls.append([dict(m) for m in messages])
        if not self._queue:
            raise AssertionError("FakeLLMClient 的预设响应已用尽，说明主循环多调了一次 LLM")
        return self._queue.pop(0)

    def chat(self, messages, tools=None) -> ChatResult:  # noqa: ARG002
        return self.chat_stream(messages)

    def get_token_usage(self) -> dict:
        return {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}


def _tool_call(name: str, arguments: dict, call_id: str = "call_1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


def test_react_loop_runs_tool_then_answers():
    """一轮工具调用后给出最终答案，且 tool 消息与 assistant(tool_calls) 严格配对。"""
    agent = ReActAgent()
    agent.llm_client = FakeLLMClient(
        [
            ChatResult(
                content="",
                tool_calls=[_tool_call("calculator", {"expression": "2 + 3 * 4"})],
                finish_reason="tool_calls",
            ),
            ChatResult(content="答案是 14", finish_reason="stop"),
        ]
    )

    answer = agent.run("算一下 2 + 3 * 4")

    assert answer == "答案是 14"
    # 一轮 = user → assistant(tool_calls) → tool → assistant(最终答案)
    roles = [m["role"] for m in agent.memory.get_messages()]
    assert roles == ["system", "user", "assistant", "tool", "assistant"], roles

    # 协议校验：assistant 的 arguments 必须是 JSON 字符串，tool 消息必须回指同一个 id
    tool_calls = [m for m in agent.memory.get_messages() if m.get("tool_calls")]
    assert len(tool_calls) == 1
    assert isinstance(tool_calls[0]["tool_calls"][0]["function"]["arguments"], str)
    tool_msgs = [m for m in agent.memory.get_messages() if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == tool_calls[0]["tool_calls"][0]["id"]
    assert "14" in tool_msgs[0]["content"]


def test_planner_prefers_submit_plan_tool_call():
    """Planner 优先读 submit_plan 的参数表。"""
    planner = Planner(FakeLLMClient([ChatResult(content="", tool_calls=[_tool_call("submit_plan", {"steps": ["查资料", "写答案"]})])]))
    assert planner.plan("帮我写个方案") == ["查资料", "写答案"]


def test_planner_falls_back_to_plain_text_json():
    """模型不调工具、正文里写 JSON 时，兜底解析仍能拿到步骤。"""
    planner = Planner(FakeLLMClient([ChatResult(content='```json\n{"steps": ["甲", "乙"]}\n```')]))
    assert planner.plan("随便") == ["甲", "乙"]


def test_plan_and_solve_runs_plan_step_by_step():
    """规划阶段走 submit_plan，执行阶段逐步返回文本，最终答案取最后一步。"""
    agent = PlanAndSolveAgent()
    agent.llm_client = FakeLLMClient(
        [
            ChatResult(content="", tool_calls=[_tool_call("submit_plan", {"steps": ["第一步", "第二步"]})]),
            ChatResult(content="第一步的结果"),
            ChatResult(content="第二步的结果"),
        ]
    )
    agent.planner.llm_client = agent.llm_client
    agent.executor.llm_client = agent.llm_client

    assert agent.run("两步骤任务") == "第二步的结果"


def test_reflection_converges_when_review_says_done():
    """反思返回 needs_improvement=false 时收敛，最终代码取最后一次执行。"""
    agent = ReflectionAgent(max_iterations=3)
    agent.llm_client = FakeLLMClient(
        [
            ChatResult(content="```python\nprint('v1')\n```"),  # 初始执行
            ChatResult(
                content="",
                tool_calls=[
                    _tool_call("submit_review", {"needs_improvement": True, "feedback": "补充边界处理"}),
                ],
            ),
            ChatResult(content="```python\nprint('v2')\n```"),  # 优化后
            ChatResult(
                content="",
                tool_calls=[
                    _tool_call("submit_review", {"needs_improvement": False, "feedback": "可以了"}),
                ],
            ),
        ]
    )

    final_code = agent.run("写一个打印脚本")

    assert final_code == "print('v2')"  # 代码围栏已被剥掉
    assert [r["type"] for r in agent.memory.records] == [
        "execution",
        "reflection",
        "execution",
        "reflection",
    ]


def test_autogen_pipeline_stops_at_terminate(tmp_path, monkeypatch):
    """四个角色各说一次，UserProxy 回复 TERMINATE 即结束。"""
    # 产物写到临时目录，不要污染仓库的 generated/
    monkeypatch.setattr("martin_agent.core.autogen_agent.OUTPUT_DIR", str(tmp_path))

    agent = AutoGenAgent()
    fake = FakeLLMClient(
        [
            ChatResult(content="需求已明确"),
            ChatResult(content="```python\n# 文件名：main.py\nprint('hi')\n```"),
            ChatResult(content="代码没问题"),
            ChatResult(content="TERMINATE"),
        ]
    )
    # 角色在 AutoGenAgent.__init__ 里各自持有客户端引用，需逐个替换
    agent.llm_client = fake
    for role in agent.agents:
        role.llm_client = fake

    reply = agent.run("写个 hello world")

    assert reply == "TERMINATE"
    # 共享历史：任务 + 四个角色的发言
    assert [m.get("name") for m in agent.history] == [
        None,
        "ProductManager",
        "Engineer",
        "CodeReviewer",
        "UserProxy",
    ]


def test_langgraph_agent_reset_swaps_thread():
    """LangGraph 模式 reset() 后会话换新（不测完整流程图，避免耦合图实现细节）。"""
    agent = LangGraphAgent()
    first = agent._thread_id
    agent.reset()
    assert agent._thread_id != first
