"""
Reflection Agent 实现（Reflexion 论文思想的简化版）。

流程：
  1. 初始执行：按任务要求生成第一版代码
  2. 迭代循环（最多 max_iterations 轮）：
     a. 反思：LLM 调用 submit_review 工具给出评审结论
              （needs_improvement / feedback）；判定无需改进则结束
     b. 优化：按反馈生成新版本代码
  3. 返回最新一版代码

对外接口与 ReActAgent 一致：run(task) / reset()。
"""

from __future__ import annotations

import json
import re

from src.core.llm_client import LLMClient
from src.core.prompts import (
    INITIAL_PROMPT_TEMPLATE,
    REFLECT_PROMPT_TEMPLATE,
    REFINE_PROMPT_TEMPLATE,
)
from src.memory.trajectory import TrajectoryMemory

# 「提交评审」工具：把「输出 JSON 评审」改成原生函数调用，
# 让模型填参数表（needs_improvement / feedback）而不是自由写 JSON。
_SUBMIT_REVIEW_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "submit_review",
            "description": "提交代码评审结论",
            "parameters": {
                "type": "object",
                "properties": {
                    "needs_improvement": {
                        "type": "boolean",
                        "description": "代码在算法层面是否仍有可改进之处",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "改进建议；无需改进时为空字符串",
                    },
                },
                "required": ["needs_improvement", "feedback"],
            },
        },
    }
]


def _parse_review(result) -> dict | None:
    """从 submit_review 工具调用取评审结论；未调用时退回解析正文 JSON。"""
    for tc in result.tool_calls:
        if tc.name == "submit_review":
            args = tc.arguments
            if isinstance(args, dict) and "needs_improvement" in args:
                return args
    text = (result.content or "").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def _strip_code_fences(text: str) -> str:
    """
    去掉模型输出里可能包裹的代码围栏，只保留代码本体。

    模型经常不遵守「直接输出代码」的约定，把代码裹进 ```python ... ```。
    入库前剥掉，否则下一轮反思时会在模板的围栏里出现嵌套围栏。
    """
    text = text.strip()
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    # 没写围栏：去掉常见的「以下是代码：」这类前缀行
    lines = text.splitlines()
    if lines and lines[0].rstrip().endswith(("：", ":")):
        lines = lines[1:]
    return "\n".join(lines).strip() or text


class ReflectionAgent:
    """执行 → 反思 → 优化 循环；对外接口：run(task) / reset()。"""

    def __init__(self, max_iterations: int = 3) -> None:
        self.llm_client = LLMClient()
        self.memory = TrajectoryMemory()  # 轨迹记忆：execution / reflection 两类记录
        self.max_iterations = max_iterations

    def run(self, task: str) -> str:
        print(f"\n--- 开始处理任务 ---\n任务: {task}")

        # --- 1. 初始执行 ---
        print("\n--- 正在进行初始尝试 ---")
        initial_code = self._get_llm_response(
            INITIAL_PROMPT_TEMPLATE.format(task=task), strip_fences=True
        )
        self.memory.add_record("execution", initial_code)

        # --- 2. 迭代循环：反思与优化 ---
        for i in range(self.max_iterations):
            print(f"\n--- 第 {i + 1}/{self.max_iterations} 轮迭代 ---")

            # a. 反思：调用 submit_review 工具提交评审结论
            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution() or ""
            verdict = self._get_review(
                REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code)
            )

            # b. 检查是否需要停止
            if verdict is None:
                # 解析失败绝不停止：按「仍需改进」处理，保持迭代推进
                feedback = "（未能收到有效的评审工具调用，按仍需改进处理）"
                needs_improvement = True
            else:
                needs = verdict.get("needs_improvement", True)
                # JSON 里模型可能把布尔写成字符串 "false"，Python 中为真值，需转换
                if isinstance(needs, str):
                    needs = needs.strip().lower() == "true"
                needs_improvement = bool(needs)
                feedback = str(verdict.get("feedback", "")).strip()

            self.memory.add_record("reflection", feedback)

            if not needs_improvement:
                print("\n✅ 反思认为代码已无需改进，任务完成。")
                break

            # c. 优化
            print("\n-> 正在进行优化...")
            refined_code = self._get_llm_response(
                REFINE_PROMPT_TEMPLATE.format(
                    task=task,
                    last_code_attempt=last_code,
                    feedback=feedback,
                ),
                strip_fences=True,
            )
            self.memory.add_record("execution", refined_code)

        final_code = self.memory.get_last_execution() or ""
        print(f"\n--- 任务完成 ---\n最终生成的代码:\n```python\n{final_code}\n```")
        return final_code

    def reset(self) -> None:
        """清空轨迹记忆（反思/执行的记录）。"""
        self.memory.clear()
        print("Agent 状态已重置")

    def _get_llm_response(self, prompt: str, strip_fences: bool = True) -> str:
        """调用 LLM 获取完整流式响应；空响应时返回占位提示。"""
        messages = [{"role": "user", "content": prompt}]
        response_text = self.llm_client.chat_stream(messages).content
        if not response_text.strip():
            print("⚠️  模型没有输出内容，本轮结果记为占位提示。")
            return "（模型未输出任何内容，请检查任务描述）"
        return _strip_code_fences(response_text) if strip_fences else response_text.strip()

    def _get_review(self, prompt: str) -> dict | None:
        """以 submit_review 函数调用方式获取评审结论；解析失败返回 None。"""
        messages = [{"role": "user", "content": prompt}]
        result = self.llm_client.chat_stream(messages, tools=_SUBMIT_REVIEW_SCHEMA)
        return _parse_review(result)
