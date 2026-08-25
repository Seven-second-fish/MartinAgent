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

    def add_message(self, role: str, content: str):
        """
        添加一条消息到历史
        
        Args:
            role: 角色，'user' / 'assistant' / 'system'
            content: 消息内容
        """
        # 模型一轮说完（assistant）之后，下一轮要继续想，必须再塞进一条「非 assistant」的消息，否则就像让助手自己跟自己说话，协议也不自然。
        self._history.append({"role": role, "content": content})

        # 超出最大轮数时，裁剪最早的记录（保留 system 消息）
        non_system = [m for m in self._history if m["role"] != "system"]
        if len(non_system) > self.max_turns * 2:
            # 删除最早的一轮（user + assistant 各一条）
            for i, msg in enumerate(self._history):
                if msg["role"] == "user":
                    self._history.pop(i)
                    if i < len(self._history) and self._history[i]["role"] == "assistant":
                        self._history.pop(i)
                    break

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