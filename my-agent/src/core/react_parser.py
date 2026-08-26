"""
ReAct 文本解析：把 LLM 的纯文本回复变成结构化结果。

返回字典的 type 只能是：
  - TYPE_ACTION         → {"type", "tool", "input"}
  - TYPE_FINAL_ANSWER   → {"type", "content"}
  - TYPE_UNKNOWN        → {"type"}

判定顺序：
  1. 完整 Action + Action Input → action（与 Final Answer 同时出现时也优先工具）
  2. Final Answer 字段 → final_answer
  3. 纯自然语言（无任何 ReAct 字段痕迹）→ 整段当作 final_answer（闲聊兜底）
  4. 其余（例如只写了半截 Action）→ unknown
"""

from __future__ import annotations

import re

TYPE_ACTION = "action"
TYPE_FINAL_ANSWER = "final_answer"
TYPE_UNKNOWN = "unknown"

# 下一结构化字段的边界（用于截取多行 Action Input / Final Answer）
_NEXT_FIELD = r"Thought|Action|Observation|Final\s*Answer"


def parse_react_response(response: str) -> dict:
    """解析 LLM 输出；返回带 type 字段的字典。"""
    text = _normalize_markdown_labels(response.strip())
    if not text:
        return {"type": TYPE_UNKNOWN}

    action = _extract_action(text)
    if action is not None:
        return action

    final = _extract_final_answer(text)
    if final is not None:
        return final

    if not _looks_like_structured_attempt(text):
        return {"type": TYPE_FINAL_ANSWER, "content": text}

    return {"type": TYPE_UNKNOWN}


def _normalize_markdown_labels(text: str) -> str:
    """
    去掉标签上的 markdown 加粗，方便后续正则匹配。

    例：
      **Action:** foo     → Action: foo
      **Final Answer**：x → Final Answer: x
    """
    return re.sub(
        r"\*\*\s*(Final\s*Answer|Action(?:\s*Input)?)\s*"
        r"(?:\*\*\s*[:：]|[:：]\s*\*\*)",
        r"\1:",
        text,
        flags=re.IGNORECASE,
    )


def _extract_action(text: str) -> dict | None:
    """提取工具调用；要求同时存在行首的 Action 与 Action Input。"""
    # 工具名允许被方括号包裹：模型常把提示词里的「Action: [工具名称]」原样照抄
    action_match = re.search(
        r"(?im)^\s*Action\s*[:：]\s*\[?\s*([A-Za-z_][\w]*)\s*\]?\s*$",
        text,
    )
    input_match = re.search(
        rf"(?im)^\s*Action\s*Input\s*[:：]\s*(.+?)"
        rf"(?=^\s*(?:{_NEXT_FIELD})\s*[:：]|\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    if not action_match or not input_match:
        return None

    # 去掉参数两端的引号/方括号（如 ['2/3/4/5/6'] → 2/3/4/5/6）
    tool_input = input_match.group(1).strip().strip("\"'[]")
    if not tool_input:
        return None

    return {
        "type": TYPE_ACTION,
        "tool": action_match.group(1).strip(),
        "input": tool_input,
    }


def _extract_final_answer(text: str) -> dict | None:
    """提取 Final Answer 正文（可多行）；找不到或为空时返回 None。"""
    final_match = re.search(
        rf"(?im)^\s*Final\s*Answer\s*[:：]\s*(.+?)"
        rf"(?=^\s*(?:Thought|Action|Observation)\s*[:：]|\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    if not final_match:
        return None

    content = final_match.group(1).strip()
    if not content:
        return None

    return {"type": TYPE_FINAL_ANSWER, "content": content}


def _looks_like_structured_attempt(text: str) -> bool:
    """
    是否出现过 ReAct 字段（Thought / Action / Final Answer 等）。

    True 表示模型在按格式写（哪怕写了一半），此时不要当成普通闲聊。
    """
    return bool(
        re.search(
            rf"(?im)^\s*(?:{_NEXT_FIELD})\s*[:：]",
            text,
        )
    )
