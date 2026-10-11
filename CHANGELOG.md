# Changelog

本项目的所有重要变更都记录在此文件。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- 为网络类工具（`web_tool` / `websearch_tool` / `get_weather`）补 mock 测试
- 给 `pytest` 增加覆盖率门槛（`fail_under`），防止覆盖率回退
- 为有副作用的工具（`file_tool` / `web_tool` / `websearch_tool`）加确认或审计记录

## [0.2.0] - 2026-10-11

### 新增

- `.github/workflows/ci.yml`：push / PR 自动在 Ubuntu + Windows × Python 3.10/3.12/3.13 上跑测试
- `LICENSE`（MIT）、`CHANGELOG.md`、`.editorconfig`
- 测试覆盖率统计（`pytest-cov`，`python -m pytest` 默认带覆盖率报告）
- `martin_agent/paths.py`：运行时目录（logs / workspace / generated）与 `.env` 统一锚定，
  不再随启动目录漂移
- `pytest` 用例拆分为 `tests/test_tools_memory.py` 与 `tests/test_stream_assembly.py`
- `tests/test_agents.py`：五种 Agent 主循环的 mock LLM 测试（覆盖率 45% → 70%）
- `requirements.txt` / `requirements-dev.txt`：由 `pip-compile` 从 `pyproject.toml`
  生成的锁文件（精确版本 + 传递依赖），用于完全可复现的环境

### 变更

- **目录归一（标准布局）**：`my-agent/src/` → `martin_agent/`，`my-agent/tests/` → `tests/`，
  `my-agent/.env.example` → `.env.example`，去掉非标准的 `my-agent/` 包装层
- **包重命名**：`src` → `martin_agent`，全部导入改为 `from martin_agent.xxx import ...`
- 打包方式改为标准 `pyproject.toml`（PEP 621），新增 `martin-agent` 命令入口，
  可在任意目录运行，不再依赖 cwd
- `file_tool` 沙箱改用绝对路径 + `Path.resolve()` 校验，修复 `..` 路径穿越
- 未配置 `OPENAI_API_KEY` 时给出可读提示，不再抛 SDK 原始异常
- 文档同步为五种 Agent 与新目录结构（README / AGENT.md / CLAUDE.md / LEARNING_PLAN.md）

### 移除

- 根目录 `logs/memory.json`（运行时产物误入库）
- `my-agent/workspace/test.txt`（沙箱内的自测残留）
- `my-agent/requirements.txt`（与根目录重复）
- 手写维护的 `requirements.txt`（改为 `pip-compile` 生成的锁文件，见「新增」）
- `pytest.ini`（配置并入 `pyproject.toml`）

### 修复

- `.gitignore` 补齐 `.env*` 通配、运行时目录内容与 `/logs/` 兜底，
  并保留各处 `.gitkeep` 占位

## [0.1.0] - 2026-09

### 新增

- ReAct、Plan-and-Solve、Reflection 三种 Agent 范式
- 原生函数调用（OpenAI `tools` 字段）承载工具调用与结构化输出
- 流式输出、`ConversationMemory` / `PersistentMemory` 双记忆实现
- 7 个内置工具：calculator / file_tool / web_tool / websearch_tool / get_time / get_weather / roll_dice
- AutoGen 风格多角色对话与 LangGraph 状态机两种扩展模式

[Unreleased]: https://github.com/Seven-second-fish/MartinAgent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Seven-second-fish/MartinAgent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Seven-second-fish/MartinAgent/releases/tag/v0.1.0
