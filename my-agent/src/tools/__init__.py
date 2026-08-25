"""
工具注册表。

约定：每个工具是一个无状态模块，导出：
  - NAME: str
  - DESCRIPTION: str
  - run(input: str) -> str
"""

from __future__ import annotations

from types import ModuleType

from src.tools import calculator, file_tool, web_tool, weather, roll_dice, search
from src.tools import time as time_tool

# Action 字段名 → 工具模块
TOOLS: dict[str, ModuleType] = {
    # "calculator": <模块 calculator.py>
    # 键（左边）：字符串 "roll_dice"（来自模块里的 NAME）
    # 值（右边）：整个模块对象，上面有 .NAME、.DESCRIPTION、.run
    calculator.NAME: calculator,
    file_tool.NAME: file_tool,
    web_tool.NAME: web_tool,
    time_tool.NAME: time_tool,
    weather.NAME: weather,
    roll_dice.NAME: roll_dice,
    search.NAME: search
}
