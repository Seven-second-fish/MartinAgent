"""
轨迹记忆：按类型（execution / reflection）存储智能体的行动与反思记录。

与 conversation.py 的 ConversationMemory（面向 LLM 协议的多轮消息历史）职责不同：
轨迹记忆只做存档，供提示词拼接使用，不直接发给 LLM。
"""


class TrajectoryMemory:
    """按记录类型存储智能体的行动与反思轨迹。"""

    def __init__(self) -> None:
        """初始化一个空列表来存储所有记录。"""
        self.records: list[dict] = []

    def add_record(self, record_type: str, content: str) -> None:
        """
        向记忆中添加一条新记录。

        参数:
        - record_type (str): 记录的类型 ('execution' 或 'reflection')。
        - content (str): 记录的具体内容 (例如，生成的代码或反思的反馈)。
        """
        record = {"type": record_type, "content": content}
        self.records.append(record)
        print(f"📝 记忆已更新，新增一条 '{record_type}' 记录。")

    def get_trajectory(self) -> str:
        """
        将所有记忆记录格式化为一个连贯的字符串文本，用于构建提示词。
        """
        trajectory_parts = []
        for record in self.records:
            if record['type'] == 'execution':
                trajectory_parts.append(f"--- 上一轮尝试 (代码) ---\n{record['content']}")
            elif record['type'] == 'reflection':
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")

        return "\n\n".join(trajectory_parts)

    def get_last_execution(self) -> str | None:
        """
        获取最近一次的执行结果 (例如，最新生成的代码)。
        如果不存在，则返回 None。
        """
        for record in reversed(self.records):
            if record['type'] == 'execution':
                return record['content']
        return None

    def clear(self) -> None:
        """清空所有记录。"""
        self.records.clear()
