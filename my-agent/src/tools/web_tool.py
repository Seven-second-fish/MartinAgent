"""
网页抓取工具：获取 URL 的纯文本片段。

无状态模块：NAME / DESCRIPTION / run()。
"""

from __future__ import annotations

import re

import requests
from urllib.parse import urlparse

NAME = "web_tool"
DESCRIPTION = (
    "获取指定 URL 的网页文本内容。"
    "输入一个完整的 URL（需包含 http:// 或 https://），"
    "返回页面的纯文本内容（前 2000 字符）。"
    "示例：'https://example.com'"
)

PARAMETERS = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "完整 URL，需含 http:// 或 https://，如 'https://example.com'",
        }
    },
    "required": ["url"],
}

TIMEOUT = 10
MAX_CONTENT_LENGTH = 2000


def run(url: str) -> str:
    """获取网页文本内容，返回截断后的纯文本或错误信息。"""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return "错误：URL 必须以 http:// 或 https:// 开头"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        text = _strip_html(response.text)
        truncated = text[:MAX_CONTENT_LENGTH]
        return f"网页内容（前{MAX_CONTENT_LENGTH}字符）：\n{truncated}"

    except requests.exceptions.Timeout:
        return f"错误：请求超时（>{TIMEOUT}秒）"
    except requests.exceptions.HTTPError as e:
        return f"错误：HTTP 请求失败，状态码 {e.response.status_code}"
    except Exception as e:
        return f"请求失败：{str(e)}"


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


if __name__ == "__main__":
    print(run("https://www.example.com"))
