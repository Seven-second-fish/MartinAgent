"""
Reflection Agent 实现（Reflexion 论文思想的简化版）。

流程：
  1. 初始执行：按任务要求生成第一版代码
  2. 迭代循环（最多 max_iterations 轮）：
     a. 反思：LLM 评审最新代码，给出改进反馈；若输出停止标记则结束
     b. 优化：按反馈生成新版本代码
  3. 返回最新一版代码

对外接口与 ReActAgent 一致：run(task) / reset()。
"""

from __future__ import annotations

import re

from src.core.llm_client import LLMClient
from src.core.prompts import (
    INITIAL_PROMPT_TEMPLATE,
    REFLECT_PROMPT_TEMPLATE,
    REFINE_PROMPT_TEMPLATE,
)
from src.memory.trajectory import TrajectoryMemory

# 反思阶段输出的「已无需再优化」停止标记（见 REFLECT_PROMPT_TEMPLATE 的停止约定）
STOP_MARKER = "NO_IMPROVEMENT_NEEDED"


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

            # a. 反思
            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution() or ""
            feedback = self._get_llm_response(
                REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code),
                strip_fences=False,
            )
            self.memory.add_record("reflection", feedback)

            # b. 检查是否需要停止：查显式标记，而不是自然语言子串
            #    （「无需改进」作为从句出现在反馈里会导致误停，模板已约定停止标记）
            if STOP_MARKER in feedback:
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
        response_text = self.llm_client.chat_stream(messages) or ""
        if not response_text.strip():
            print("⚠️  模型没有输出内容，本轮结果记为占位提示。")
            return "（模型未输出任何内容，请检查任务描述）"
        return _strip_code_fences(response_text) if strip_fences else response_text.strip()
