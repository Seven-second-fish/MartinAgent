"""
工具注册表。

约定：每个工具是一个无状态模块，导出：
  - NAME: str
  - DESCRIPTION: str
  - PARAMETERS: JSON Schema（函数调用的参数定义，0 或 1 个参数）
  - run(input: str) -> str

中心化辅助：
  - build_tool_schemas()：生成 OpenAI tools 字段格式
  - call_tool(name, args)：按名称调用工具（args 字典 → 单字符串输入）
"""

from __future__ import annotations

from types import ModuleType

from src.tools import calculator, file_tool, web_tool, weather, roll_dice, search
from src.tools import time as time_tool

# 工具名 → 工具模块
TOOLS: dict[str, ModuleType] = {
    # 键（左边）：字符串 "calculator"（来自模块里的 NAME）
    # 值（右边）：整个模块对象，上面有 .NAME、.DESCRIPTION、.PARAMETERS、.run
    calculator.NAME: calculator,
    file_tool.NAME: file_tool,
    web_tool.NAME: web_tool,
    time_tool.NAME: time_tool,
    weather.NAME: weather,
    roll_dice.NAME: roll_dice,
    search.NAME: search
}

_EMPTY_PARAMETERS = {"type": "object", "properties": {}}


def build_tool_schemas() -> list[dict]:
    """生成 OpenAI tools 字段格式（每个工具一条 function schema）。"""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.DESCRIPTION,
                "parameters": getattr(tool, "PARAMETERS", _EMPTY_PARAMETERS),
            },
        }
        for name, tool in TOOLS.items()
    ]


def call_tool(name: str, args: dict) -> str:
    """
    按名称调用已注册工具模块；args 字典 → 单字符串输入（run(str) 协议不变）。

    未知工具或异常时返回错误字符串（供模型自纠）。
    """
    if name not in TOOLS:
        return f"错误：工具 '{name}' 不存在。可用工具：{', '.join(TOOLS.keys())}"

    if len(args) == 1:
        tool_input = str(next(iter(args.values())))
    elif args:
        # 多参数兜底：拼成 "k=v" 形式，尽量保留信息
        tool_input = " ".join(f"{k}={v}" for k, v in args.items())
    else:
        tool_input = ""

    try:
        return TOOLS[name].run(tool_input)
    except Exception as e:
        return f"工具执行异常：{str(e)}"
