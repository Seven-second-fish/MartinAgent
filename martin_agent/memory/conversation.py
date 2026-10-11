"""
对话记忆模块
管理 Agent 的上下文历史，支持长度限制和摘要压缩
"""


class ConversationMemory:
    """对话历史管理"""

    def __init__(self, max_turns: int = 20, system_prompt: str = ""):
        """
        Args:
            max_turns: 最大保留的对话轮数（超出后自动裁剪旧记录）
            system_prompt: 系统提示词
        """
        self.max_turns = max_turns
        self.system_prompt = system_prompt
        self._history: list[dict] = []

    def add_message(self, role: str, content: str, **extra):
        """
        添加一条消息到历史

        Args:
            role: 角色，'user' / 'assistant' / 'tool' / 'system'
            content: 消息内容
            extra: 附加字段，透传进消息字典
                   （如 assistant 的 tool_calls、tool 的 tool_call_id）
        """
        msg = {"role": role, "content": content}
        msg.update(extra)
        self._history.append(msg)
        self._trim()

    def _trim(self):
        """
        按「轮」裁剪历史：一轮 = 一条 user 起、到下一条 user 之前的所有消息。

        保留最近 max_turns 个完整轮。tool 消息永远不会与它的
        assistant(tool_calls) 拆散；旧的孤儿消息会挂在最早的轮里被一并裁掉。
        """
        turns: list[list[dict]] = []
        current: list[dict] = []
        for msg in self._history:
            if msg.get("role") == "user" and current:
                turns.append(current)
                current = []
            current.append(msg)
        if current:
            turns.append(current)
        if len(turns) > self.max_turns:
            self._history = [m for turn in turns[-self.max_turns:] for m in turn]

    def get_messages(self) -> list[dict]:
        """
        获取完整的消息列表（包含 system prompt）

        Returns:
            适合直接传给 LLM 的消息列表
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self._history)
        return messages

    def clear(self):
        """清空对话历史"""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)

    def __repr__(self) -> str:
        return f"ConversationMemory(turns={len(self._history)//2}, max={self.max_turns})"

if __name__ == "__main__":
    memory = ConversationMemory(max_turns=10)
    memory.add_message("user", "Hello, how are you?")
    memory.add_message("assistant", "I'm good, thank you!")
    print(memory.get_messages())
    memory.clear()
    print(memory.get_messages())
