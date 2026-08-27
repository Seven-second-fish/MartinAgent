"""
持久化记忆模块
管理 Agent 的持久化历史，让 Agent 在重启后还能记住之前的对话
"""

import json
import os

from src.memory.conversation import ConversationMemory

# 继承于 ConversationMemory，实现持久化记忆
class PersistentMemory(ConversationMemory):
    """支持持久化的对话记忆"""

    def __init__(
        self,
        save_path: str = "./logs/memory.json",
        max_turns: int = 20,
        system_prompt: str = "",
    ):
        super().__init__(max_turns=max_turns, system_prompt=system_prompt)
        self.save_path = save_path
        self._load()  # 启动时自动加载历史

    def add_message(self, role: str, content: str, **extra):
        super().add_message(role, content, **extra)
        self._save()  # 每次添加消息后自动保存

    def clear(self):
        super().clear()
        self._save()  # 清空后同步写入磁盘

    def _save(self):
        directory = os.path.dirname(self.save_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                self._history = json.load(f)
            print(f"已加载 {len(self._history)} 条历史记录")
        except (json.JSONDecodeError, OSError) as e:
            print(f"加载历史记录失败，将使用空记忆：{e}")
            self._history = []
