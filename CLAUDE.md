# CLAUDE.md — MartinAgent

面向 AI 编程助手的项目说明。修改本仓库时代码与约定以本文为准；面向人类的简介见 `README.md`。

## 项目概述

MartinAgent 是一个命令行 Agent 框架，内置五种 agent（pythonpath 根：仓库根目录的 `martin_agent/` 包）：

| 模式 | 名称 | 文件 | 说明 |
|:---:|---|---|---|
| `1` | ReAct | `martin_agent/core/react_agent.py` | Thought → Action → Observation 循环 |
| `2` | Plan-and-Solve | `martin_agent/core/plan_solve_agent.py` | Planner 提交计划 → Executor 逐步执行 |
| `3` | Reflection | `martin_agent/core/reflection_agent.py` | 执行 → 反思 → 优化 |
| `4` | AutoGen 风格 | `martin_agent/core/autogen_agent.py` | 多角色共享历史轮流对话（纯手写，不依赖 AutoGen 库） |
| `5` | LangGraph | `martin_agent/core/langgraph_agent.py` | 状态机 / 有向图范式（**唯一**使用第三方框架的模式） |

工具调用与结构化输出都走 API 原生函数调用（OpenAI `tools` 字段）。

- 入口：`martin_agent/main.py`（`AGENTS` 注册表 + REPL）
- 提示词：`martin_agent/core/prompts.py`
- LLM：`martin_agent/core/llm_client.py`（OpenAI 兼容 API，流式输出 + 原生工具调用组装）
- 记忆：默认 `ConversationMemory`；可切换 `PersistentMemory`（落盘到 `logs/memory.json`）
- 路径：所有运行时目录与 `.env` 统一由 `martin_agent/paths.py` 锚定
- 工具：`martin_agent/tools/` 下的无状态模块（见下方约定）

## 目录约定

```text
MartinAgent/
├── pyproject.toml            # 包元数据、依赖、entry point、pytest/覆盖率配置（唯一来源）
├── requirements.txt          # pip-compile 生成的锁文件（核心依赖精确版本）
├── requirements-dev.txt      # pip-compile 生成的锁文件（dev + langgraph）
├── LICENSE                   # MIT
├── CHANGELOG.md              # 变更记录（Keep a Changelog 风格）
├── .gitattributes            # 换行符规范化（仓库内 LF）
├── .editorconfig             # 跨编辑器统一缩进/换行
├── VERSION                   # 版本号，被 pyproject.toml 动态读取
├── AGENT.md / CLAUDE.md      # 仓库约定（两份内容一致）
├── README.md / LEARNING_PLAN.md
├── .github/workflows/ci.yml  # CI：Ubuntu + Windows × Python 3.10/3.12/3.13 跑测试
├── martin_agent/             # 📦 包根（import martin_agent）
│   ├── main.py               # 入口：模式选择 + REPL
│   ├── paths.py              # 路径与环境变量统一入口
│   ├── core/                 # 各 agent + llm_client + prompts
│   ├── tools/                # 无状态工具模块
│   └── memory/               # conversation / persistentmemory / trajectory
├── tests/                    # pytest 用例（conftest.py + test_*.py）
├── .env / .env.example       # .env 不入库；.env.example 是环境变量权威清单
├── pyrightconfig.json
├── workspace/                # file_tool 唯一允许读写的沙箱（内容不入库）
├── generated/                # autogen 模式生成的代码（内容不入库）
└── logs/                     # 运行时记忆与日志（内容不入库）
```

不要提交虚拟环境 `.venv/`、`.env*`、`__pycache__/`、
`{logs,workspace,generated}/**`（各处只保留 `.gitkeep`）。

## 包与导入（重要）

- 包名是 **`martin_agent`**，位于仓库根目录（标准 src-flat 布局，无中间包装目录）。
  `pyproject.toml` 里配置 `testpaths = ["tests"]`，`tests/` 与包平级。
- 包内一律用**绝对导入**：`from martin_agent.core.llm_client import LLMClient`。
  **不要**再用 `from src...`，也**不要**为跑通而写 `sys.path.insert`。
- 首次使用先装包：`pip install -e ".[dev,langgraph]"`（只想跑核心四种模式可省 `langgraph`）。
  装完 `martin-agent` 命令与 `python -m martin_agent.main` 都能在任意目录运行。
- 新增子包时，在 `martin_agent/` 下建目录 + `__init__.py` 即可，无需改 `pyproject.toml`。

## 路径约定（重要）

- **一切运行时目录都从 `martin_agent/paths.py` 取**：`LOGS_DIR` / `WORKSPACE_DIR` / `GENERATED_DIR` /
  `MEMORY_FILE` / `ENV_FILE`。不要在新代码里写 `"./logs/..."` 这类依赖 cwd 的相对路径。
- 原因：相对路径会让产物落点随「在哪个目录启动 python」漂移
  （历史事故：在仓库根目录启动过，根目录多出一个 `logs/memory.json`）。
- `load_dotenv` 只在 `martin_agent/paths.py` 里调用一次，且显式传 `ENV_FILE`；
  其余模块 `from martin_agent.paths import ENV_FILE` 即可（导入即生效），不要各自 `load_dotenv()`。

## 环境与命令

在仓库根目录操作：

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1

# 装成本地包（推荐）：之后可在任意目录运行
pip install -e ".[dev,langgraph]"    # 只跑核心四种模式可省 langgraph

cp .env.example .env                 # 填好 OPENAI_API_KEY 等
martin-agent                         # 等价：python -m martin_agent.main
```

跑测试（仓库根目录，配置来自 `pyproject.toml`，默认带覆盖率报告）：

```bash
python -m pytest
python -m pytest -v --no-cov         # 只看用例名、跳过覆盖率
```

环境变量（`.env`，权威清单见 `.env.example`）：

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `MODEL_NAME`
- `WEB_SEARCH_API`（`websearch_tool` 可选）
- `DEFAULT_CITY`（天气工具可选）

依赖：核心是 `openai`、`python-dotenv`、`requests`、`colorama`；
测试需 `pytest` + `pytest-cov`；模式 5 额外需要 `langchain-core`、`langgraph`。

**依赖的三层分工（重要，别搞混）**：

| 文件 | 角色 | 谁维护 |
|---|---|---|
| `pyproject.toml` | **意图**：需要哪些库、版本范围、extras 分组 | 人写，唯一源头 |
| `requirements.txt` | **锁定**：核心依赖的精确版本（含传递依赖） | `pip-compile` 生成，勿手改 |
| `requirements-dev.txt` | **锁定**：`dev` + `langgraph` extras 的精确版本 | `pip-compile` 生成，勿手改 |

改依赖的流程：先改 `pyproject.toml`，再重新生成锁文件（在仓库根目录执行）：

```bash
pip install pip-tools        # 仅生成锁文件时需要
pip-compile --strip-extras --output-file requirements.txt pyproject.toml
pip-compile --strip-extras --extra dev --extra langgraph --output-file requirements-dev.txt pyproject.toml
```

装依赖二选一：日常开发用 `pip install -e ".[dev,langgraph]"`；
需要**完全可复现**的环境（CI、换机器、排障）用 `pip install -r requirements-dev.txt`。

## 架构约定

### 类 vs 模块（重要）

| 用类 | 用模块 + 函数 |
|------|----------------|
| 需要跨调用保存可变状态 | 无状态、一次算完就返回 |
| 各 `*Agent`、`LLMClient`、`ConversationMemory`、`PersistentMemory`、`TrajectoryMemory` | `paths`、`prompts`、各 `tools/*` |

不要为了「看起来像 OOP」给无状态逻辑套空类。

### 添加工具

1. 在 `martin_agent/tools/` 新增模块，导出：
   - `NAME: str`
   - `DESCRIPTION: str`（注入 system prompt，写清输入格式与示例）
   - `PARAMETERS: dict`（JSON Schema，0 或 1 个参数，与 `run(str)` 协议对应；
     无参工具用 `{"type": "object", "properties": {}}`）
   - `run(input: str) -> str`
2. 在 `martin_agent/tools/__init__.py` 的 `TOOLS` 字典中注册（`build_tool_schemas()` 自动生成 OpenAI tools 字段）。
3. 工具应返回可读字符串；异常在工具内转为错误信息，避免抛穿 Agent 循环。
4. 目前共 7 个工具；增删工具后同步更新 `tests/test_tools_memory.py` 里的数量断言与 `README.md` 的工具表。

### 输出协议（重要）

- 工具调用：走 API 原生函数调用（`tools` 字段），LLM 返回结构化 `tool_calls`，
  **不要**再用纯文本 `Action:` / `Action Input:` 让模型输出。
- 结构化输出同样走函数调用：Planner 用 `submit_plan` 工具提交 `steps` 数组，
  Reflection 用 `submit_review` 工具提交 `needs_improvement` / `feedback`，
  让模型填参数表而不是自由写 JSON，从源头避免字段瞎编/解析错误。
- assistant 历史消息里的 `tool_calls[].function.arguments` 必须是 JSON **字符串**
  （勿存解析后的 dict）；每个工具调用后必须跟一条 `role="tool"`、
  `tool_call_id` 匹配的消息，否则 API 报错。

### Agent 行为

- 协议：工具调用与结构化输出都走原生函数调用（见上方「输出协议」）。
- 新增 agent 模式：实现 `run(task) / reset()`，在 `martin_agent/core/__init__.py` 导出，
  再在 `martin_agent/main.py` 的 `AGENTS` 注册表加一行（提示文字自动跟着变）。
- `MAX_ITERATIONS`（ReAct）/ `MAX_TOOL_ROUNDS`（Executor 单步内）/ `MAX_ROUNDS`（AutoGen 流水线轮数）
  分别控制各模式的循环上限。
- `reset` 清空记忆；改持久化路径时改 `martin_agent/paths.py` 的 `MEMORY_FILE`，不要在 `PersistentMemory` 里写死。

### 记忆

- `ConversationMemory`：内存历史 + 轮数裁剪。
- `PersistentMemory`：继承前者，每次 `add_message` / `clear` 落盘到 `MEMORY_FILE`。
- `TrajectoryMemory`：只做轨迹存档供提示词拼接（Reflection 用），不发给 LLM。
- 切换记忆实现时，改 `react_agent.py` 中的构造即可。
- 记忆裁剪按「轮」进行（一轮 = user 起到下一条 user 前），tool 消息永远不会与其
  `assistant(tool_calls)` 拆散，不会产生孤儿 tool 消息。

### 安全边界

- **禁止**把真实 API Key 写入文档、示例或提交 `.env`。
- `file_tool` 只能操作 `WORKSPACE_DIR`（`<repo>/workspace`），且必须拒绝 `..` 路径穿越；
  不要扩大到仓库其他目录，除非用户明确要求并做好路径校验。
- `web_tool` 仅允许 `http`/`https`；保持超时与内容长度限制。

## 代码风格

- Python 3.10+；模块顶部中文 docstring 说明职责。
- 有状态用类，无状态用函数；少抽象、不过度框架化。
- 用户可见终端输出可继续使用 `colorama`；库代码避免无关打印。
- 测试用 pytest + `assert`，不引入额外测试框架。
- 不主动新增 README/文档，除非用户要求；改行为时更新本文件（及 `AGENT.md`）中与约定冲突的部分。

## 不要做的事

- 不要提交或打印 `.env` 中的密钥。
- 不要往核心路径引入重型 Agent 框架（LangChain / AutoGen 等），除非用户明确要求；
  现有 `langgraph_agent.py` 是模式 5 的**可选**学习用例，不要在其余模式里扩散框架依赖。
- 不要把 `.venv` / `__pycache__` / 运行时目录内容加回版本库。
- 不要用正则解析模型输出的协议文本（原生函数调用已覆盖所有协议场景，含 Planner/Reflection 的结构化输出）；
  唯一的例外是 `_strip_code_fences`、autogen 的代码块提取这类纯外观/内容清理。
- 不要在业务代码里写 `"./logs"` `"./workspace"` 之类依赖 cwd 的路径（见「路径约定」）。
- 不要把无状态工具再改回空壳类。

## 快速自检

- [ ] `pip install -e ".[dev,langgraph]"` 可安装，`martin-agent` 命令可用
- [ ] 配置 `.env` 后 `martin-agent`（任意目录）可启动，五种模式都能选
- [ ] `python -m pytest`（仓库根目录）全绿，覆盖率不低于当前水平（约 70%）
- [ ] 新增 Agent / 工具后，`tests/` 里有对应用例
- [ ] 包内没有残留 `from src...` 导入，也没有 `sys.path.insert` 之类的兜底写法
- [ ] 新工具已写入 `TOOLS`，且 `DESCRIPTION` 含输入示例、`PARAMETERS` 与 `run` 参数一致
- [ ] Planner / Reflection 的结构化输出已走 `submit_plan` / `submit_review` 函数调用
- [ ] 新代码没有引入依赖 cwd 的相对路径
- [ ] `git status` 干净，运行时目录内容未被纳入版本库
