"""
天气工具
让 Agent 能够获取指定城市或当前位置的天气，避免大模型的幻觉
"""

import os
from urllib.parse import quote

import requests


class WeatherTool:
    """获取天气（支持指定城市 / 当前位置）"""

    name = "get_weather"
    description = (
        "查询天气。输入城市名称（中文或英文），返回简要天气信息。"
        "若用户未提及城市（例如「今天天气怎么样」），"
        "Action Input 请填「当前」，将查询默认城市或按网络位置推断的当前城市。"
        "示例：'北京'、'Shanghai'、'当前'"
    )

    # 表示「查当前位置」的输入
    CURRENT_ALIASES = {"", "当前", "本地", "当前位置", "current", "here", "local"}

    def run(self, city: str) -> str:
        city = (city or "").strip()
        if city.lower() in self.CURRENT_ALIASES:
            city = self._resolve_current_city()
            location_hint = city or "网络位置"
        else:
            location_hint = city

        try:
            # 城市为空时，wttr.in 会按请求方公网 IP 自动定位
            path = quote(city) if city else ""
            url = f"https://wttr.in/{path}?format=3&lang=zh"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return f"天气信息（{location_hint}）：{response.text.strip()}"
        except Exception as e:
            return f"天气查询失败：{e}"

    def _resolve_current_city(self) -> str:
        """
        解析「当前城市」：
        1. 优先读环境变量 DEFAULT_CITY（最准确，适合个人 Agent）
        2. 未配置则返回空字符串，交给 wttr.in 按 IP 定位
        """
        return (os.getenv("DEFAULT_CITY") or "").strip()
