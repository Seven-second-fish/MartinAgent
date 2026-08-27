"""
Plan-and-Solve Agent 实现。

流程：
  1. Planner 规划：把用户问题拆成一个有序步骤列表（调用 submit_plan 工具提交 steps）
  2. Executor 执行：按步骤逐个让 LLM 求解，把已完成步骤和结果当作历史传给下一步；
     单步内可多轮调用工具（原生函数调用），工具结果自动返回
  3. PlanAndSolveAgent 组装：先规划、后执行，返回最终答案

对外接口与 ReActAgent 一致：run(task) / reset()。
"""

from __future__ import annotations

import json
import re

from src.core.llm_client import LLMClient
from src.core.prompts import EXECUTOR_PROMPT_TEMPLATE, PLANNER_PROMPT_TEMPLATE
from src.tools import TOOLS, build_tool_schemas, call_tool

# 「提交计划」工具：把「输出 JSON 计划」改成原生函数调用，
# 让模型填参数表（steps 数组）而不是自由写 JSON，从源头避免字段瞎编/解析错误。
_SUBMIT_PLAN_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "submit_plan",
            "description": "提交分解好的行动计划步骤列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "按逻辑顺序排列的子任务步骤",
                    }
                },
                "required": ["steps"],
            },
        },
    }
]


def _extract_plan(result) -> list[str]:
    """
    从 submit_plan 工具调用中取步骤列表。

    优先读工具调用参数（模型填好的参数表）；模型偶尔不调工具、直接在正文写 JSON，
    此时退化为解析正文兜底。仍失败返回空列表。
    """
    for tc in result.tool_calls:
        if tc.name == "submit_plan":
            steps = tc.arguments.get("steps")
            if isinstance(steps, list):
                return [str(s) for s in steps]

    text = (result.content or "").strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if match:
        text = match.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("steps"), list):
            return [str(s) for s in data["steps"]]
    except json.JSONDecodeError:
        pass
    return []


class Planner:
    """规划阶段：把用户问题拆成有序的步骤列表。"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def plan(self, question: str) -> list[str]:
        """根据用户问题生成行动计划；未收到有效工具调用时重试一次，仍失败返回空列表。"""
        print("--- 正在生成计划 ---")

        prompt = PLANNER_PROMPT_TEMPLATE.format(
            question=question,
            tool_descriptions="\n".join(
                f"- **{name}**：{tool.DESCRIPTION}"
                for name, tool in TOOLS.items()
            ),
        )
        # 规划阶段是一次性提问，没有多轮对话，直接构造消息即可
        messages = [{"role": "system", "content": prompt}]
        result = self.llm_client.chat_stream(messages, tools=_SUBMIT_PLAN_SCHEMA)
        plan = _extract_plan(result)

        if not plan:
            # 未收到有效计划：追加纠正提示，要求模型务必调用 submit_plan 工具
            retry_prompt = prompt + (
                "\n\n你刚才没有调用 submit_plan 工具。"
                "请务必直接调用 submit_plan 工具，把步骤列表作为 steps 参数提交。"
            )
            print("❌ 未收到有效的计划工具调用，正在要求模型重试…")
            result = self.llm_client.chat_stream(
                [{"role": "system", "content": retry_prompt}],
                tools=_SUBMIT_PLAN_SCHEMA,
            )
            plan = _extract_plan(result)

        if plan:
            print("✅ 计划已生成：")
            for i, step in enumerate(plan, start=1):
                print(f"   {i}. {step}")
        else:
            print(f"❌ 计划解析失败，原始响应：{result.content}")
        return plan


class Executor:
    """执行阶段：按计划逐步求解，把历史步骤和结果传给下一步。"""

    # 单个步骤内最多允许的工具调用轮数（防止模型无限调用工具）
    MAX_TOOL_ROUNDS = 3

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
            # 单步内本地消息列表：允许同一步骤内多轮工具调用（错误可重试）
            messages = [{"role": "system", "content": prompt}]

            step_answer = ""
            last_observation = ""
            for _ in range(self.MAX_TOOL_ROUNDS):
                result = self.llm_client.chat_stream(
                    messages, tools=build_tool_schemas()
                )

                # 模型发起工具调用：执行并把结果以 tool 消息写回，继续同一步骤
                if result.tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": result.content or "",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(
                                            tc.arguments, ensure_ascii=False
                                        ),
                                    },
                                }
                                for tc in result.tool_calls
                            ],
                        }
                    )
                    for tc in result.tool_calls:
                        print(f"🔧 调用工具：{tc.name}，参数：{tc.arguments}")
                        observation = call_tool(tc.name, tc.arguments)
                        print(f"📋 工具返回：{observation}\n")
                        last_observation = observation
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": observation,
                            }
                        )
                    continue

                # 文本回复即该步答案
                step_answer = result.content.strip() or "（无输出）"
                break
            else:
                # 工具调用轮数耗尽：以最后一次工具返回作为该步结果
                step_answer = last_observation or "（无输出）"

            response_text = step_answer
            history += f"步骤 {i}: {step}\n结果: {step_answer}\n\n"

            print(f"✅ 步骤 {i} 已完成")

        # 最后一步的答案即最终答案
        return response_text


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
