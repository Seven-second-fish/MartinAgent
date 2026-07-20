"""
工具注册表。

约定：每个工具是一个无状态模块，导出：
  - NAME: str
  - DESCRIPTION: str
  - run(input: str) -> str
"""

from __future__ import annotations

from types import ModuleType

from src.tools import calculator, file_tool, web_tool, weather
from src.tools import time as time_tool

# Action 字段名 → 工具模块
TOOLS: dict[str, ModuleType] = {
    calculator.NAME: calculator,
    file_tool.NAME: file_tool,
    web_tool.NAME: web_tool,
    time_tool.NAME: time_tool,
    weather.NAME: weather,
}
