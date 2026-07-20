"""
天气工具：查询城市或当前位置天气。

无状态模块：NAME / DESCRIPTION / run()。
"""

from __future__ import annotations

import os
from urllib.parse import quote

import requests

NAME = "get_weather"
DESCRIPTION = (
    "查询天气。输入城市名称（中文或英文），返回简要天气信息。"
    "若用户未提及城市（例如「今天天气怎么样」），"
    "Action Input 请填「当前」，将查询默认城市或按网络位置推断的当前城市。"
    "示例：'北京'、'Shanghai'、'当前'"
)

_CURRENT_ALIASES = {"", "当前", "本地", "当前位置", "current", "here", "local"}


def run(city: str) -> str:
    """查询天气，返回简要信息或错误信息。"""
    city = (city or "").strip()
    if city.lower() in _CURRENT_ALIASES:
        city = _resolve_current_city()
        location_hint = city or "网络位置"
    else:
        location_hint = city

    try:
        path = quote(city) if city else ""
        url = f"https://wttr.in/{path}?format=3&lang=zh"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return f"天气信息（{location_hint}）：{response.text.strip()}"
    except Exception as e:
        return f"天气查询失败：{e}"


def _resolve_current_city() -> str:
    """优先读 DEFAULT_CITY；未配置则交由 wttr.in 按 IP 定位。"""
    return (os.getenv("DEFAULT_CITY") or "").strip()
