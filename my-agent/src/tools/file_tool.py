"""
文件读写工具：仅允许操作 my-agent/workspace 沙箱。

无状态模块：NAME / DESCRIPTION / run()。
沙箱位置由 src/paths.py 锚定，与启动目录无关。
"""

from __future__ import annotations

import os
from pathlib import Path

from src.paths import WORKSPACE_DIR

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

ALLOWED_DIR: Path = WORKSPACE_DIR


def _resolve_inside_sandbox(name: str) -> Path | None:
    """把用户给的相对路径解析到沙箱内；越界或非法返回 None。"""
    candidate = (ALLOWED_DIR / name).resolve()
    if candidate == ALLOWED_DIR or ALLOWED_DIR in candidate.parents:
        return candidate
    return None


def run(command: str) -> str:
    """执行 read/write 命令，返回结果或错误信息。"""
    os.makedirs(ALLOWED_DIR, exist_ok=True)

    parts = command.split(":", 2)
    if len(parts) < 2:
        return "命令格式错误，请使用 'read:文件路径' 或 'write:文件路径:文件内容'"

    action = parts[0].strip().lower()
    target = _resolve_inside_sandbox(parts[1].strip())
    if target is None:
        return "错误：不允许访问工作目录以外的文件"

    if action == "read":
        return _read_file(target)
    if action == "write":
        if len(parts) < 3:
            return "错误：写入操作需要提供文件内容"
        return _write_file(target, parts[2])
    return f"错误：不支持的操作类型 '{action}'，请使用 'read' 或 'write'"


def _read_file(path: Path) -> str:
    if not path.is_file():
        return f"错误：文件 '{path}' 不存在"
    try:
        content = path.read_text(encoding="utf-8")
        return f"文件内容：\n{content}"
    except Exception as e:
        return f"读取失败：{str(e)}"


def _write_file(path: Path, content: str) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"成功写入文件：{path}（{len(content)} 字符）"
    except Exception as e:
        return f"写入失败：{str(e)}"


if __name__ == "__main__":
    print(run("write:test.txt:Hello, Agent World!"))
    print(run("read:test.txt"))
