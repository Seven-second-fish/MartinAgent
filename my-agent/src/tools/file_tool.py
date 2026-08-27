"""
文件读写工具：仅允许操作 ./workspace 沙箱。

无状态模块：NAME / DESCRIPTION / run()。
"""

from __future__ import annotations

import os

NAME = "file_tool"
DESCRIPTION = (
    "读取或写入本地文件。"
    "操作类型：'read'（读取文件内容）或 'write'（写入内容到文件）。"
    "输入格式：'read:文件路径' 或 'write:文件路径:文件内容'"
)

PARAMETERS = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "'read:文件路径' 或 'write:文件路径:文件内容'",
        }
    },
    "required": ["command"],
}

ALLOWED_DIR = "./workspace"


def run(command: str) -> str:
    """执行 read/write 命令，返回结果或错误信息。"""
    os.makedirs(ALLOWED_DIR, exist_ok=True)

    parts = command.split(":", 2)
    if len(parts) < 2:
        return "命令格式错误，请使用 'read:文件路径' 或 'write:文件路径:文件内容'"

    action = parts[0].strip().lower()
    file_path = os.path.join(ALLOWED_DIR, parts[1].strip())

    if not os.path.abspath(file_path).startswith(os.path.abspath(ALLOWED_DIR)):
        return "错误：不允许访问工作目录以外的文件"

    if action == "read":
        return _read_file(file_path)
    if action == "write":
        if len(parts) < 3:
            return "错误：写入操作需要提供文件内容"
        return _write_file(file_path, parts[2])
    return f"错误：不支持的操作类型 '{action}'，请使用 'read' 或 'write'"


def _read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"错误：文件 '{path}' 不存在"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"文件内容：\n{content}"
    except Exception as e:
        return f"读取失败：{str(e)}"


def _write_file(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功写入文件：{path}（{len(content)} 字符）"
    except Exception as e:
        return f"写入失败：{str(e)}"


if __name__ == "__main__":
    print(run("write:test.txt:Hello, Agent World!"))
    print(run("read:test.txt"))
