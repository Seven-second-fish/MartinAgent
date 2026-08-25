"""
网页搜索工具：基于 bocha-web-search 的网页搜索引擎。

无状态模块：NAME / DESCRIPTION / run()。
"""

from __future__ import annotations

import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

NAME = "websearch_tool"
DESCRIPTION = (
    "网页搜索引擎。输入自然语言查询，返回最相关的 3 条网页结果（标题、链接、摘要文本），"
    "摘要完整、结果准确，更适合AI使用。"
    "用户提出需要实时信息或网上资料的问题时调用此工具（例如新闻、教程、资料查询），"
    "闲聊内容不需要调用。拿到结果后请直接整理回答，不要重复搜索。"
)

API_URL = "https://api.bocha.cn/v1/web-search"
TIMEOUT = 10
MAX_RESULTS = 3  # 最多格式化的结果条数
MAX_CONTENT_LENGTH = 200  # 单条结果摘要的最大字符数


def run(query: str) -> str:
    """搜索网页，把结果解析成紧凑文本返回；失败时返回错误信息。"""
    query = (query or "").strip()
    if not query:
        return "错误：搜索关键词不能为空。"

    print(f"🔍 正在执行网页搜索: {query}")
    api_key = os.getenv("WEB_SEARCH_API")
    if not api_key:
        return "错误:WEB_SEARCH_API 未在 .env 文件中配置。"

    try:
        response = requests.post(
            API_URL,
            json={"query": query, "summary": True, "count": 5},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        # bocha 外层信封：code=200 表示成功，非 200 时 data 为空且 msg 说明原因
        code = payload.get("code")
        if code is not None and code != 200:
            return f"搜索失败: {payload.get('msg') or f'code={code}'}"
        return _format_results(payload)
    except requests.RequestException as e:
        return f"搜索请求失败: {e}"
    except ValueError as e:
        return f"搜索响应解析失败: {e}"

def _clean(text: str) -> str:
    """把文本中的换行、多空格等连续空白折叠成单个空格。"""
    return re.sub(r"\s+", " ", text).strip()


def _format_results(data: dict) -> str:
    """把 bocha 的搜索结果解析成紧凑文本；无结果时返回提示。"""
    pages = data.get("data", {}).get("webPages", {}).get("value", [])
    if not pages:
        return "对不起，没有找到相关信息。"

    lines = []
    for i, page in enumerate(pages[:MAX_RESULTS], start=1):
        title = _clean(page.get("name") or page.get("title") or "")
        url = (page.get("url") or "").strip()
        summary = _clean(page.get("summary") or page.get("snippet") or "")
        site = _clean(page.get("siteName") or "")
        date = (page.get("datePublished") or "")[:10]  # 只保留 YYYY-MM-DD
        meta = " | ".join(part for part in (site, date) if part)
        head = f"[{i}] {title}\n{url}"
        if meta:
            head += f"\n{meta}"
        lines.append(f"{head}\n{summary[:MAX_CONTENT_LENGTH]}")
    return "\n\n".join(lines)
