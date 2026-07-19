"""
网络请求工具
让 Agent 能够获取网页内容（简化版）
"""

import requests
from urllib.parse import urlparse


class WebTool:
    """网络请求工具"""

    name = "web_tool"
    description = (
        "获取指定 URL 的网页文本内容。"
        "输入一个完整的 URL（需包含 http:// 或 https://），"
        "返回页面的纯文本内容（前 2000 字符）。"
        "示例：'https://example.com'"
    )

    TIMEOUT = 10  # 请求超时时间（秒）
    MAX_CONTENT_LENGTH = 2000  # 最大返回内容长度

    def run(self, url: str) -> str:
        """
        获取网页内容
        
        Args:
            url: 目标 URL
            
        Returns:
            网页文本内容或错误信息
        """
        # 验证 URL 格式
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
            response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            # 简单提取文本（去除 HTML 标签）
            text = self._strip_html(response.text)
            truncated = text[: self.MAX_CONTENT_LENGTH]

            return f"网页内容（前{self.MAX_CONTENT_LENGTH}字符）：\n{truncated}"

        except requests.exceptions.Timeout:
            return f"错误：请求超时（>{self.TIMEOUT}秒）"
        except requests.exceptions.HTTPError as e:
            return f"错误：HTTP 请求失败，状态码 {e.response.status_code}"
        except Exception as e:
            return f"请求失败：{str(e)}"

    def _strip_html(self, html: str) -> str:
        """简单去除 HTML 标签"""
        import re
        # 去除 script 和 style 标签及其内容
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
        # 去除所有 HTML 标签
        html = re.sub(r"<[^>]+>", " ", html)
        # 合并多余空白
        html = re.sub(r"\s+", " ", html).strip()
        return html

if __name__ == "__main__":
    tool = WebTool()
    print(tool.run("https://www.baidu.com"))