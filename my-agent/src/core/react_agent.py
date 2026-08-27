"""
ReAct Agent 核心实现。

主循环：
  用户任务 → LLM 输出（原生函数调用）→ 分支处理
    ├─ tool_calls：执行工具，把结果以 tool 消息写回记忆，进入下一轮
    ├─ 空内容：提示模型重新输出，进入下一轮
    └─ 文本回复：作为最终答案返回

工具调用走 API 原生函数调用（tools 字段），不再解析纯文本 Action 格式。
"""

from __future__ import annotations

import json
from datetime import datetime

from colorama import Fore, Style, init

from src.core.llm_client import ChatResult, LLMClient
from src.core.prompts import SYSTEM_PROMPT
from src.memory.conversation import ConversationMemory
from src.memory.persistentmemory import PersistentMemory  # noqa: F401  # 切换持久化记忆时取消注释下方写法
from src.tools import TOOLS, build_tool_schemas, call_tool

init(autoreset=True)


class ReActAgent:
    """
    基于 ReAct（Reasoning + Acting）的 Agent。

    持有可变状态：tools 注册表、llm 客户端、对话记忆。
    对外接口：run(task) / reset()。
    """

    MAX_ITERATIONS = 8

    def __init__(self) -> None:
        self.tools = TOOLS
        self.llm_client = LLMClient()

        # 将tools目录下.py的DESCRIPTION组合到system prompt中，让模型知道有这个工具，怎么用
        tool_descriptions = "\n".join(
            f"- **{name}**：{tool.DESCRIPTION}"
            for name, tool in self.tools.items()
        )
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = SYSTEM_PROMPT.format(
            tool_descriptions=tool_descriptions, current_date=current_date
        )

        # 默认：进程内记忆（重启后丢失）
        self.memory = ConversationMemory(max_turns=20, system_prompt=system_prompt)

        # 若要持久化到磁盘，改用：
        # self.memory = PersistentMemory(max_turns=20, system_prompt=system_prompt)

    def run(self, task: str) -> str:
        """
        处理用户任务：多轮「调用 LLM → 执行工具/结束」，直到给出最终答案
        或达到 MAX_ITERATIONS。
        """
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"🤖 任务开始：{task}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")

        self.memory.add_message("user", task)

        for round_idx in range(1, self.MAX_ITERATIONS + 1):
            print(f"{Fore.YELLOW}---第{round_idx}轮思考---{Style.RESET_ALL}")

            result = self.llm_client.chat_stream(
                self.memory.get_messages(), tools=build_tool_schemas()
            )
            print()

            # 分支1：模型发起工具调用 → 执行并写回记忆，继续下一轮
            if result.tool_calls:
                self._run_tools_and_remember(result)
                continue

            # 分支2：LLM 偶尔返回空内容（上下文过长或偶发异常），单独提示重试
            if not result.content.strip():
                print(f"{Fore.RED}⚠️  LLM 返回空内容，要求其重新输出{Style.RESET_ALL}")
                self.memory.add_message(
                    "user",
                    "你刚才没有输出任何内容。请重新思考并输出回答，"
                    "如果任务需要，也可以发起工具调用。",
                )
                continue

            # 分支3：文本回复即最终答案
            return self._finish_with_answer(result)

        fallback = "任务未能在规定步骤内完成，请尝试简化任务描述。"
        print(f"\n{Fore.RED}⚠️  {fallback}{Style.RESET_ALL}\n")
        return fallback

    def reset(self) -> None:
        """清空对话历史。"""
        self.memory.clear()
        print("Agent 状态已重置")

    def _finish_with_answer(self, result: ChatResult) -> str:
        """打印完成信息，返回最终答案。"""
        self.memory.add_message("assistant", result.content)
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print("✅ 任务完成！")
        print(f"最终答案：{result.content}")
        print(f"Token 消耗：{self.llm_client.get_token_usage()}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")
        return result.content

    def _run_tools_and_remember(self, result: ChatResult) -> None:
        """
        执行模型发起的所有工具调用，并把 assistant 原文 + 各工具结果写回记忆。

        协议要求：assistant 消息必须带原始 tool_calls（arguments 为 JSON 字符串），
        每个工具调用后跟一条 role="tool" 且 tool_call_id 匹配的消息。
        """
        self.memory.add_message(
            "assistant",
            result.content or "",
            tool_calls=[
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in result.tool_calls
            ],
        )

        for tc in result.tool_calls:
            print(f"{Fore.MAGENTA}🔧 调用工具：{tc.name}")
            print(f"   参数：{tc.arguments}{Style.RESET_ALL}")

            observation = call_tool(tc.name, tc.arguments)
            print(f"{Fore.BLUE}📋 工具返回：{observation}{Style.RESET_ALL}\n")

            self.memory.add_message("tool", observation, tool_call_id=tc.id)
