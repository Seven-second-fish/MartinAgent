"""
Plan-and-Solve Agent 实现。

流程：
  1. Planner 规划：把用户问题拆成一个有序步骤列表（Python 列表字面量）
  2. Executor 执行：按步骤逐个让 LLM 求解，把已完成步骤和结果当作历史传给下一步
  3. PlanAndSolveAgent 组装：先规划、后执行，返回最终答案

对外接口与 ReActAgent 一致：run(task) / reset()。
"""

from __future__ import annotations

import ast
import re
from datetime import datetime

from src.core.llm_client import LLMClient
from src.core.prompts import EXECUTOR_PROMPT_TEMPLATE, PLANNER_PROMPT_TEMPLATE
from src.tools import TOOLS
from src.core.react_parser import TYPE_ACTION, parse_react_response


def _extract_plan_text(text: str) -> str:
    """
    从 LLM 输出中提取列表字面量文本，按优先级：
      1. 代码围栏内容（```python ... ```）
      2. 中括号片段（模型没写围栏，但把列表夹在说明文字中间时）
      3. 全文（本来就是纯列表）
    """
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()


def _parse_plan(response_text: str) -> list[str]:
    """把 LLM 输出解析成步骤列表；解析失败返回空列表。"""
    text = _extract_plan_text(response_text)
    # 第一次直接解析；失败时去掉字符串内的真实换行再试一次
    # （模型偶尔会把步骤写成多行字符串，真实换行在字符串字面量里不合法）
    for candidate in (text, text.replace("\n", "")):
        try:
            plan = ast.literal_eval(candidate)
            if isinstance(plan, list):
                return plan
        except (ValueError, SyntaxError):
            continue
    return []


class Planner:
    """规划阶段：把用户问题拆成有序的步骤列表。"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def plan(self, question: str) -> list[str]:
        """根据用户问题生成行动计划；解析失败时返回空列表。"""
        print("--- 正在生成计划 ---")

        prompt = PLANNER_PROMPT_TEMPLATE.format(
            current_date=datetime.now().strftime("%Y-%m-%d"),
            question=question,
            tool_descriptions="\n".join(
                f"- **{name}**：{tool.DESCRIPTION}"
                for name, tool in TOOLS.items()
            ),
        )
        # 规划阶段是一次性提问，没有多轮对话，直接构造消息即可
        messages = [{"role": "system", "content": prompt}]
        response_text = self.llm_client.chat_stream(messages) or ""

        plan = _parse_plan(response_text)
        if plan:
            print("✅ 计划已生成：")
            for i, step in enumerate(plan, start=1):
                print(f"   {i}. {step}")
        else:
            print(f"❌ 计划解析失败，原始响应：{response_text}")
        return plan


class Executor:
    """执行阶段：按计划逐步求解，把历史步骤和结果传给下一步。"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.tools = TOOLS

    def execute(self, question: str, plan: list[str]) -> str:
        """按计划逐步执行；返回最后一步的答案。"""
        history = ""  # 已完成步骤及结果的字符串历史

        print("\n--- 正在执行计划 ---")
        response_text = ""
        tool_descriptions = "\n".join(
            f"- **{name}**：{tool.DESCRIPTION}"
            for name, tool in self.tools.items()
        )
        for i, step in enumerate(plan, start=1):
            print(f"\n-> 正在执行步骤 {i}/{len(plan)}: {step}")

            prompt = EXECUTOR_PROMPT_TEMPLATE.format(
                question=question,
                plan="\n".join(f"{idx}. {s}" for idx, s in enumerate(plan, start=1)),
                history=history or "无",
                current_step=step,
                tool_descriptions=tool_descriptions,
            )
            messages = [{"role": "system", "content": prompt}]

            response_text = self.llm_client.chat_stream(messages) or "（无输出）"

            # Plan-and-Solve 里每一步都是一次求解，只有一种特例：
            # 模型需要工具时输出 Action，工具返回的 Observation 即作为该步结果
            parsed = parse_react_response(response_text)
            if parsed["type"] == TYPE_ACTION:
                print(f"🔧 调用工具：{parsed['tool']}，输入：{parsed['input']}")
                observation = self._execute_tool(parsed["tool"], parsed["input"])
                print(f"📋 工具返回：{observation}\n")
                response_text = f"Observation: {observation}"

            history += f"步骤 {i}: {step}\n结果: {response_text}\n\n"

            print(f"✅ 步骤 {i} 已完成")

        # 最后一步的答案即最终答案
        return response_text

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """按名称调用已注册工具模块；未知工具或异常时返回错误字符串。"""
        if tool_name not in self.tools:
            available = ", ".join(self.tools.keys())
            return f"错误：工具 '{tool_name}' 不存在。可用工具：{available}"

        try:
            return self.tools[tool_name].run(tool_input)
        except Exception as e:
            return f"工具执行异常：{str(e)}"


class PlanAndSolveAgent:
    """Plan-and-Solve 智能体：先规划、后执行。对外接口：run() / reset()。"""

    def __init__(self):
        self.llm_client = LLMClient()
        self.planner = Planner(self.llm_client)
        self.executor = Executor(self.llm_client)

    def run(self, question: str) -> str:
        """运行完整流程：规划 → 执行；返回最终答案。"""
        print(f"\n--- 开始处理问题 ---\n问题: {question}")

        plan = self.planner.plan(question)
        if not plan:
            fallback = "无法生成有效的行动计划，请尝试简化问题描述。"
            print(f"\n--- 任务终止 ---\n{fallback}")
            return fallback

        final_answer = self.executor.execute(question, plan)
        print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")
        return final_answer

    def reset(self) -> None:
        """
        对外接口（与 ReActAgent 一致）。

        Plan-and-Solve 每次 run 相互独立（规划/执行都在单次 run 内完成），
        工具调用结果只记在单次 run 的局部 history 里，没有跨 run 状态，无需清理。
        """
        print("Agent 状态已重置")
