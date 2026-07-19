"""
文件读写工具
让 Agent 能够读取和写入本地文件
"""

import os

class FileTool:
    """文件操作工具"""

    name = "file_tool"

    description = (
        "读取或写入本地文件。"
        "操作类型：'read'（读取文件内容）或 'write'（写入内容到文件）。"
        "输入格式：'read:文件路径' 或 'write:文件路径:文件内容'"
    )

    # 限制可操作的目录（安全沙箱）
    ALLOWED_DIR = "./workspace"

    def __init__(self):
        # 确保工作目录存在
        os.makedirs(self.ALLOWED_DIR, exist_ok=True)

    def run(self, command: str) -> str:
        """
        执行文件操作
        
        Args:
            command: 命令字符串，格式为 'read:文件路径' 或 'write:文件路径:文件内容'
            
        Returns:
            操作结果字符串，或错误信息
        """
        parts = command.split(":", 2)
        if len(parts) < 2:
            return "命令格式错误，请使用 'read:文件路径' 或 'write:文件路径:文件内容'"

        action = parts[0].strip().lower()
        file_path = os.path.join(self.ALLOWED_DIR, parts[1].strip())

        # 安全检查：防止路径穿越攻击
        if not os.path.abspath(file_path).startswith(
            os.path.abspath(self.ALLOWED_DIR)
        ):
            return "错误：不允许访问工作目录以外的文件"

        if action == "read":
            return self._read_file(file_path)
        elif action == "write":
            if len(parts) < 3:
                return "错误：写入操作需要提供文件内容"
            content = parts[2]
            return self._write_file(file_path, content)
        else:
            return f"错误：不支持的操作类型 '{action}'，请使用 'read' 或 'write'"
    
    def _read_file(self, path: str) -> str:
        """读取文件"""
        if not os.path.exists(path):
            return f"错误：文件 '{path}' 不存在"
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return f"文件内容：\n{content}"
        except Exception as e:
            return f"读取失败：{str(e)}"

    def _write_file(self, path: str, content: str) -> str:
        """写入文件"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"成功写入文件：{path}（{len(content)} 字符）"
        except Exception as e:
            return f"写入失败：{str(e)}"

if __name__ == "__main__":
    tool = FileTool()
    print(tool.run("write:test.txt:Hello, Agent World!"))
    print(tool.run("read:test.txt"))