"""
时间工具
让 Agent 能够获取当前时间，避免大模型的幻觉

"""
from datetime import datetime

class TimeTool:
    """获取当前时间"""

    name = "get_time"
    description = "获取当前的日期和时间，无需输入参数，直接调用即可"

    def run(self, _: str = "") -> str:
        now = datetime.now()

        return f"当前时间：{now.strftime("%年-%月-%日 %时:%分:%秒")}"