"""
掷塞子工具：返回1~6的随机证书

"""

from __future__ import annotations

import random

NAME = "roll_dice"
DESCRIPTION = (
    "掷一个六面骰子，返回 1～6 的真实随机结果。"
    "仅当用户明确要求「掷/再掷/roll」时调用本工具；禁止自己编造点数。"
    "若用户问「刚才/上一次」的点数：只根据对话历史里的工具返回结果回答；"
    "历史中没有记录则说明没有，禁止为此再次调用本工具。"
    "无需输入参数，直接调用即可。"
)

PARAMETERS = {"type": "object", "properties": {}}

def run(_: str = "") -> str:
    value = random.randint(1, 6)
    return f"掷塞子结果：{value}"
