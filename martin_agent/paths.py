"""
项目路径与环境变量统一入口。

约定：所有运行时目录都锚定到本文件位置（仓库根目录），不依赖「在哪个目录启动 python」。
这样从任意 cwd 启动，产物都落在同一处：

    logs/       运行时记忆与日志（不入版本库）
    workspace/  file_tool 唯一允许读写的沙箱（不入版本库）
    generated/  autogen 模式生成的代码目录（不入版本库）
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 本文件：<repo>/martin_agent/paths.py → parents[1] 即仓库根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

LOGS_DIR: Path = PROJECT_ROOT / "logs"
WORKSPACE_DIR: Path = PROJECT_ROOT / "workspace"
GENERATED_DIR: Path = PROJECT_ROOT / "generated"

MEMORY_FILE: Path = LOGS_DIR / "memory.json"
ENV_FILE: Path = PROJECT_ROOT / ".env"

# 显式指定 .env 位置，避免 load_dotenv() 顺着 cwd 向上找、误加载别的项目配置
load_dotenv(ENV_FILE)


def ensure_runtime_dirs() -> None:
    """创建运行时目录（logs / workspace / generated），幂等。"""
    for directory in (LOGS_DIR, WORKSPACE_DIR, GENERATED_DIR):
        os.makedirs(directory, exist_ok=True)
