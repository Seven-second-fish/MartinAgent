"""
计算器工具
让 Agent 能够执行数学计算，避免大模型的计算幻觉
"""

import math

class CalculatorTool:
    """安全的数学计算工具"""

    name = "calculator"
    description = (
        "执行数学计算。输入一个数学表达式字符串，返回计算结果。"
        "支持：加减乘除、幂运算、开方、三角函数等。"
        "示例输入：'2 + 3 * 4'、'sqrt(16)'、'sin(3.14/2)'"
    )

    # 允许使用的安全函数白名单
    SAFE_FUNCTIONS = {
        "abs": abs, "round": round,
        "sqrt": math.sqrt, "pow": math.pow,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "log2": math.log2,
        "pi": math.pi, "e": math.e,
        "ceil": math.ceil, "floor": math.floor,
    }

    def __init__(self) -> None:
        pass

    def run(self, expression: str) -> str:
        """
        执行数学计算
        
        Args:
            expression: 数学表达式字符串
            
        Returns:
            计算结果字符串，或错误信息
        """
        try:
            result = eval(expression, {"__builtins__": {}}, self.SAFE_FUNCTIONS)
            return f"计算结果: {expression} = {result}"
        except ZeroDivisionError:
            return "计算错误: 除数不能为0"
        except Exception as e:
            return f"计算错误: {str(e)}, 请检查表达式格式"

if __name__ == "__main__":
    calc = CalculatorTool()
    print(calc.run("2 + 3 * 4"))
    print(calc.run("sqrt(16)"))
    print(calc.run("sin(3.14/2)"))
    print(calc.run("3/0"))