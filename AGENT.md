# AGENT.md — MartinAgent

面向 AI 编程助手的项目说明。修改本仓库时代码与约定以本文为准；面向人类的简介见 `README.md`。

## 项目概述

MartinAgent 是一个命令行 Agent 框架，内置三种 agent（ReAct / Plan-and-Solve / Reflection），
工具调用与结构化输出都走 API 原生函数调用（OpenAI `tools` 字段）。

- 入口：`my-agent/main.py`
- 核心：`my-agent/src/core/react_agent.py`（`ReActAgent` 主循环）、`plan_solve_agent.py`、`reflection_agent.py`
- 提示词：`my-agent/src/core/prompts.py`
- LLM：`my-agent/src/core/llm_client.py`（OpenAI 兼容 API，流式输出 + 原生工具调用组装）
- 记忆：默认 `ConversationMemory`；可切换 `PersistentMemory`（`logs/memory.json`）
- 工具：`my-agent/src/tools/` 下的无状态模块（见下方约定）

## 目录约定

```text
MartinAgent/
├── requirements.txt          # 依赖声明（根目录）
├── AGENT.md                  # 本文件
├── README.md
└── my-agent/
    ├── main.py
    ├── .env / .env.example
    ├── workspace/            # file_tool 唯一允许写入的沙箱
    ├── logs/                 # 运行时记忆与日志（勿提交内容）
    └── src/
        ├── core/
        ├── tools/
        └── memory/
```

不要把虚拟环境 `agent-env/`、`.env`、`__pycache__/`、`logs/*`（除 `.gitkeep`）提交进 Git。

## 环境与命令

在仓库根目录操作：

```bash
python3 -m venv agent-env
source agent-env/bin/activate
pip install -r requirements.txt
cp my-agent/.env.example my-agent/.env   # 若尚无 .env
cd my-agent && python main.py
```

环境变量（`my-agent/.env`）：

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `MODEL_NAME`
- `DEFAULT_CITY`（天气工具可选）

依赖主要是：`openai`、`python-dotenv`、`requests`、`colorama`。新增第三方库时同步更新根目录 `requirements.txt`。

## 架构约定

### 类 vs 模块（重要）

| 用类 | 用模块 + 函数 |
|------|----------------|
| 需要跨调用保存可变状态 | 无状态、一次算完就返回 |
| `ReActAgent`、`LLMClient`、`ConversationMemory`、`PersistentMemory` | `prompts`、各 `tools/*` |

不要为了「看起来像 OOP」给无状态逻辑套空类。

### 添加工具

1. 在 `my-agent/src/tools/` 新增模块，导出：
   - `NAME: str`
   - `DESCRIPTION: str`（注入 system prompt，写清输入格式与示例）
   - `PARAMETERS: dict`（JSON Schema，0 或 1 个参数，与 `run(str)` 协议对应；
     无参工具用 `{"type": "object", "properties": {}}`）
   - `run(input: str) -> str`
2. 在 `src/tools/__init__.py` 的 `TOOLS` 字典中注册（`build_tool_schemas()` 自动生成 OpenAI tools 字段）。
3. 工具应返回可读字符串；异常在工具内转为错误信息，避免抛穿 Agent 循环。

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
- `MAX_ITERATIONS`（ReAct）/ `MAX_TOOL_ROUNDS`（Executor 单步内）控制最大工具循环次数。
- `reset` 清空记忆；改持久化路径时同步改 `PersistentMemory`。

### 记忆

- `ConversationMemory`：内存历史 + 轮数裁剪。
- `PersistentMemory`：继承前者，每次 `add_message` / `clear` 落盘。
- 切换记忆实现时，改 `react_agent.py` 中的构造即可。
- 记忆裁剪按「轮」进行（一轮 = user 起到下一条 user 前），tool 消息永远不会与其
  `assistant(tool_calls)` 拆散，不会产生孤儿 tool 消息。

### 安全边界

- **禁止**把真实 API Key 写入文档、示例或提交 `.env`。
- `file_tool` 只能操作 `./workspace`；不要扩大到仓库其他目录，除非用户明确要求并做好路径校验。
- `web_tool` 仅允许 `http`/`https`；保持超时与内容长度限制。

## 代码风格

- Python 3.10+；模块顶部中文 docstring 说明职责。
- 有状态用类，无状态用函数；少抽象、不过度框架化。
- 用户可见终端输出可继续使用 `colorama`；库代码避免无关打印。
- 不主动新增 README/文档，除非用户要求；改行为时更新本文件中与约定冲突的部分。

## 不要做的事

- 不要提交或打印 `.env` 中的密钥。
- 不要引入重型 Agent 框架（LangChain 等）除非用户明确要求。
- 不要把 `agent-env` 或 `__pycache__` 加回版本库。
- 不要用正则解析模型输出的协议文本（原生函数调用已覆盖所有协议场景，含 Planner/Reflection 的结构化输出）；
  唯一的例外是 `_strip_code_fences` 这类纯外观清理（剥代码围栏）。
- 不要把无状态工具再改回空壳类。

## 快速自检

- [ ] `pip install -r requirements.txt` 可安装
- [ ] 配置 `.env` 后 `cd my-agent && python main.py` 可启动
- [ ] 新工具已写入 `TOOLS`，且 `DESCRIPTION` 含输入示例、`PARAMETERS` 与 `run` 参数一致
- [ ] Planner / Reflection 的结构化输出已走 `submit_plan` / `submit_review` 函数调用
- [ ] 未改动 `.gitignore` 对密钥与缓存的保护
