"""
ReAct Agent 核心实现。

主循环：
  用户任务 → LLM 输出 → 解析结果 → 分支处理
    ├─ final_answer：结束并返回给用户
    ├─ action：调用工具，把 Observation 写回记忆，进入下一轮
    └─ unknown：提示模型修正格式，进入下一轮
"""

from __future__ import annotations

from datetime import datetime

from colorama import Fore, Style, init

from src.core.llm_client import LLMClient
from src.core.prompts import SYSTEM_PROMPT
from src.core.react_parser import (
    TYPE_ACTION,
    TYPE_FINAL_ANSWER,
    parse_react_response,
)
from src.memory.conversation import ConversationMemory
from src.memory.persistentmemory import PersistentMemory  # noqa: F401  # 切换持久化记忆时取消注释下方写法
from src.tools import TOOLS

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
        处理用户任务：多轮「调用 LLM → 解析 → 执行/结束」，直到给出最终答案
        或达到 MAX_ITERATIONS。
        """
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"🤖 任务开始：{task}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")

        self.memory.add_message("user", task)

        for round_idx in range(1, self.MAX_ITERATIONS + 1):
            print(f"{Fore.YELLOW}---第{round_idx}轮思考---{Style.RESET_ALL}")
            print(f"{Fore.GREEN}LLM 输出：{Style.RESET_ALL}")
            response = self.llm_client.chat_stream(self.memory.get_messages())
            print()

            # LLM 偶尔返回空内容（上下文过长或偶发异常），单独提示重试，避免浪费本轮
            if not response.strip():
                print(f"{Fore.RED}⚠️  LLM 返回空内容，要求其重新输出{Style.RESET_ALL}")
                self.memory.add_message(
                    "user",
                    "你刚才没有输出任何内容。请重新思考，"
                    "并严格按照 Thought/Action/Action Input 或 Final Answer 格式输出。",
                )
                continue

            parsed = parse_react_response(response)
            result_type = parsed["type"]

            # 分支1，如果type类型是最终答案，则直接返回最终答案并记忆
            if result_type == TYPE_FINAL_ANSWER:
                return self._finish_with_answer(response, parsed["content"])

            # 分支2，如果type类型是动作，则执行调用工具的操作并将结果记入记忆
            if result_type == TYPE_ACTION:
                self._run_tool_and_remember(response, parsed["tool"], parsed["input"])
                continue

            # 分支3，如果type类型是未知，则提示模型修正格式
            self._ask_format_retry(response)

        fallback = "任务未能在规定步骤内完成，请尝试简化任务描述。"
        print(f"\n{Fore.RED}⚠️  {fallback}{Style.RESET_ALL}\n")
        return fallback

    def reset(self) -> None:
        """清空对话历史。"""
        self.memory.clear()
        print("Agent 状态已重置")

    def _finish_with_answer(self, raw_response: str, answer: str) -> str:
        """记录助手回复，打印完成信息，返回最终答案。"""
        self.memory.add_message("assistant", raw_response)
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print("✅ 任务完成！")
        print(f"最终答案：{answer}")
        print(f"Token 消耗：{self.llm_client.get_token_usage()}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")
        return answer

    def _run_tool_and_remember(
        self, raw_response: str, tool_name: str, tool_input: str
    ) -> None:
        """执行工具，并把 LLM 原文 + Observation 写入记忆。"""
        print(f"{Fore.MAGENTA}🔧 调用工具：{tool_name}")
        print(f"   输入：{tool_input}{Style.RESET_ALL}")

        observation = self._execute_tool(tool_name, tool_input)
        print(f"{Fore.BLUE}📋 工具返回：{observation}{Style.RESET_ALL}\n")

        # 对话习惯是user → assistant → user → assistant → …
        # 模型一轮说完（assistant）之后，下一轮要继续想，必须再塞进一条「非 assistant」的消息，否则就像让助手自己跟自己说话，协议也不自然。
        self.memory.add_message("assistant", raw_response)
        self.memory.add_message("user", f"Observation: {observation}")

    def _ask_format_retry(self, raw_response: str) -> None:
        """解析失败：保存原文，追加格式纠正提示。"""
        print(f"{Fore.RED}⚠️  输出格式解析失败，提示 LLM 修正{Style.RESET_ALL}")
        self.memory.add_message("assistant", raw_response)
        self.memory.add_message(
            "user",
            "你的输出格式不正确。请严格按照 Thought/Action/Action Input 或 Final Answer 格式回复。",
        )

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """按名称调用已注册工具模块；未知工具或异常时返回错误字符串。"""
        if tool_name not in self.tools:
            available = ", ".join(self.tools.keys())
            return f"错误：工具 '{tool_name}' 不存在。可用工具：{available}"

        try:
            # 调用工具模块的run方法，并传入tool_input参数
            return self.tools[tool_name].run(tool_input)
        except Exception as e:
            return f"工具执行异常：{str(e)}"
