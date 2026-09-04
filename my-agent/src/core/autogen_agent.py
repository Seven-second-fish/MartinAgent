"""
AutoGen 风格的多智能体对话（最简实现）。

AutoGen 的核心思想只有三点：
  1. 每个角色是一个「名字 + 系统提示词」的可对话智能体（ConversableAgent）
  2. 所有角色共享同一段对话历史，轮流发言
  3. 用终止词（TERMINATE）结束对话，或达到轮数上限兜底

这里复用 prompts.py 里已定义好的四个角色，跑一条顺序流水线：
    ProductManager → Engineer → CodeReviewer → UserProxy → TERMINATE
对话结束后，把 Engineer 输出的每个 ``` 代码块保存到项目内的
generated/<时间戳>/ 新文件夹（多文件各自成文件）。

文件名规则（参考 GitHub 上 AutoGen 官方 Code Executor / 角色对话类项目的通行做法）：
  - 代码块正上方的 "# 文件名：xxx" 标记行优先（prompts.py 已要求 Engineer 输出该标记）
  - 无标记时按围栏语言取默认名（python→main.py、html→index.html、js→main.js）
  - 同一文件名重复出现视为「改进后的新版本」，直接覆盖（最终版为准）

对外接口与其它 Agent 一致：run(task) / reset()。
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from colorama import Fore, Style, init

from src.core.llm_client import LLMClient
from src.core.prompts import (
    PRODUCT_PROMPT,
    ENGINEER_PROMPT,
    CODEREVIEWER,
    USERPROXY,
)

init(autoreset=True)

# 终止词：UserProxy 测试完成后回复它，对话即结束（AutoGen 的默认约定也是 TERMINATE）
TERMINATE = "TERMINATE"

# 代码保存目录：定位到 my-agent/generated（相对本文件向上三级），与运行目录无关
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(_BASE_DIR, "generated")

# 只把 Engineer 说出的代码视为「交付物」（避免审查员复述代码导致重复保存）
CODE_AUTHOR = "Engineer"

# 文件名标记行：可带 # / // / <!-- 等注释前缀，兼容中英文关键词和全半角冒号
_FILENAME_MARK_RE = re.compile(
    r"^\s*(?:#|//|/\*|<!--|\*)?\s*(?:文件名|文件|filename|file)\s*[:：]\s*([^\s`]+)"
)

# 代码块：```语言 + 换行 + 内容 + ```；(?s) 让 . 匹配换行。
# 不能用 ^ 锚定开头，否则 finditer 在一条消息里只能匹配第一个代码块
_BLOCK_RE = re.compile(r"(?s)(.*?)```(\w*)[ \t]*\r?\n(.*?)```")

# 围栏语言 → 默认文件名（无标记行时兜底）
_LANG_DEFAULT_FILE = {
    "python": "main.py",
    "py": "main.py",
    "html": "index.html",
    "htm": "index.html",
    "js": "main.js",
    "javascript": "main.js",
}


class ConversableAgent:
    """一个可对话角色：名字 + 系统提示词。"""

    def __init__(self, name: str, system_prompt: str, llm_client: LLMClient) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.llm_client = llm_client

    def reply(self, history: list[dict]) -> str:
        """基于完整共享历史生成一次回复，返回纯文本。"""
        messages = [{"role": "system", "content": self.system_prompt}, *history]
        return self.llm_client.chat_stream(messages).content.strip()


class AutoGenAgent:
    """多角色顺序对话编排器。对外接口：run(task) / reset()。"""

    # 最多跑几轮完整流水线（一轮 = 四个角色各说一次），防止永远不出现 TERMINATE
    MAX_ROUNDS = 4

    def __init__(self) -> None:
        self.llm_client = LLMClient()
        # 角色表：列表顺序即发言顺序
        self.agents = [
            ConversableAgent("ProductManager", PRODUCT_PROMPT, self.llm_client),
            ConversableAgent("Engineer", ENGINEER_PROMPT, self.llm_client),
            ConversableAgent("CodeReviewer", CODEREVIEWER, self.llm_client),
            ConversableAgent("UserProxy", USERPROXY, self.llm_client),
        ]
        self.history: list[dict] = []

    def run(self, task: str) -> str:
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"🤖 多智能体任务开始：{task}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")

        # 共享历史：用户任务作为第一条消息，所有角色都看得到
        self.history = [{"role": "user", "content": task}]

        for round_idx in range(1, self.MAX_ROUNDS + 1):
            print(f"{Fore.YELLOW}---第{round_idx}轮对话---{Style.RESET_ALL}")

            for agent in self.agents:
                print(f"\n{Fore.GREEN}【{agent.name}】{Style.RESET_ALL}")
                # chat_stream 内部会流式打印正文，这里只负责拿回文本
                reply = agent.reply(self.history)
                # name 字段让下一位发言者知道这条是谁说的（AutoGen 同款做法）
                self.history.append(
                    {"role": "assistant", "content": reply, "name": agent.name}
                )

                # 出现终止词 → 对话结束
                if TERMINATE in reply:
                    self._save_generated_code()
                    self._print_done()
                    return reply

        fallback = "多智能体对话未在限定轮数内结束，请尝试简化任务描述。"
        print(f"\n{Fore.RED}⚠️  {fallback}{Style.RESET_ALL}\n")
        # 未正常终止时，也尽力把已有代码存下来
        self._save_generated_code()
        return fallback

    def reset(self) -> None:
        """清空共享对话历史。"""
        self.history.clear()
        print("Agent 状态已重置")

    def _extract_code_files(self) -> list[tuple[str | None, str, str]]:
        """
        抽取交付代码，返回 [(文件名标记或 None, 语言, 代码)]。

        只扫 CODE_AUTHOR 的发言，按时间顺序遍历；解析每个代码块时，
        取其正上方最近一行找 "# 文件名：xxx" 标记。代码块按顺序返回。
        """
        files: list[tuple[str | None, str, str]] = []
        for msg in self.history:
            if msg.get("role") != "assistant" or msg.get("name") != CODE_AUTHOR:
                continue
            content = msg.get("content", "")
            for head, lang, code in _BLOCK_RE.findall(content):
                filename = self._find_filename_marker(head)
                files.append((filename, lang.strip().lower(), code.strip()))
        return files

    @staticmethod
    def _find_filename_marker(head: str) -> str | None:
        """在代码块上方的文本里找文件名标记行（只看最后三行，避开前面的代码）。"""
        lines = [ln for ln in head.splitlines() if ln.strip()]
        for line in lines[-3:]:
            match = _FILENAME_MARK_RE.match(line)
            if match:
                return AutoGenAgent._safe_relative(match.group(1))
        return None

    @staticmethod
    def _safe_relative(name: str) -> str | None:
        """清洗文件名：允许子目录（src/app.py），拒绝绝对路径与 .. 逃逸。"""
        name = name.strip().strip("/\\").replace("\\", "/")
        parts = [p for p in name.split("/") if p not in ("", ".", "..")]
        return "/".join(parts) if parts else None

    def _save_generated_code(self) -> list[str]:
        """把每个交付代码块写入 generated/<时间戳>/，返回保存的文件路径列表。

        同名文件重复出现视为改进版本，直接覆盖（最终版为准）。
        """
        files = self._extract_code_files()
        if not files:
            print(f"{Fore.YELLOW}⚠️  Engineer 未输出代码块，跳过保存。{Style.RESET_ALL}")
            return []

        folder = os.path.join(OUTPUT_DIR, datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(folder, exist_ok=True)

        saved: list[str] = []
        for filename, lang, code in files:
            if not filename:
                filename = _LANG_DEFAULT_FILE.get(lang) or f"code.{lang or 'txt'}"
            path = os.path.join(folder, filename)
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            saved.append(path)
            print(f"💾 已保存：{path}")

        if saved:
            print(f"\n{Fore.CYAN}📁 本次生成的项目目录：{folder}{Style.RESET_ALL}")
        return saved

    def _print_done(self) -> None:
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print("✅ 多智能体任务完成！")
        print(f"Token 消耗：{self.llm_client.get_token_usage()}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")
