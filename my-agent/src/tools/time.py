"""
时间工具：返回当前本地日期时间。

无状态模块：NAME / DESCRIPTION / run()。
"""

from __future__ import annotations

from datetime import datetime

NAME = "get_time"
DESCRIPTION = "获取当前的日期和时间，无需输入参数，直接调用即可"


def run(_: str = "") -> str:
    """返回当前本地时间字符串。"""
    now = datetime.now()
    return f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
