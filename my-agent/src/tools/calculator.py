"""
计算器工具：执行数学表达式，避免大模型心算幻觉。

无状态模块：NAME / DESCRIPTION / run()。
"""

from __future__ import annotations

import math

NAME = "calculator"
DESCRIPTION = (
    "执行数学计算。输入一个数学表达式字符串，返回计算结果。"
    "所有算术运算都必须使用本工具，禁止心算；"
    "除数为0、语法错误等非法输入会返回错误提示。"
    "支持：加减乘除、幂运算、开方、三角函数等。"
    "示例输入：'2 + 3 * 4'、'sqrt(16)'、'sin(3.14/2)'"
)

PARAMETERS = {
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "数学表达式，如 '2 + 3 * 4'",
        }
    },
    "required": ["expression"],
}

_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "pow": math.pow,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "pi": math.pi,
    "e": math.e,
    "ceil": math.ceil,
    "floor": math.floor,
}


def run(expression: str) -> str:
    """执行数学计算，返回结果或错误信息。"""
    try:
        result = eval(expression, {"__builtins__": {}}, _SAFE_FUNCTIONS)
        return f"计算结果: {expression} = {result}"
    except ZeroDivisionError:
        return "计算错误: 除数不能为0"
    except Exception as e:
        return f"计算错误: {str(e)}, 请检查表达式格式"


if __name__ == "__main__":
    print(run("2 + 3 * 4"))
    print(run("sqrt(16)"))
    print(run("sin(3.14/2)"))
    print(run("3/0"))
