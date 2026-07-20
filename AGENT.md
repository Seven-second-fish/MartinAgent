# AGENT.md — MartinAgent

面向 AI 编程助手的项目说明。修改本仓库时代码与约定以本文为准；面向人类的简介见 `README.md`。

## 项目概述

MartinAgent 是一个命令行 **ReAct Agent**（Thought → Action → Observation → Final Answer）。

- 入口：`my-agent/main.py`
- 核心：`my-agent/src/core/agent.py`（`ReActAgent` 主循环）
- 解析：`my-agent/src/core/react_parser.py`（ReAct 文本 → action / final_answer）
- 提示词：`my-agent/src/core/prompts.py`
- LLM：`my-agent/src/core/llm_client.py`（OpenAI 兼容 API，支持流式输出）
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
| `ReActAgent`、`LLMClient`、`ConversationMemory`、`PersistentMemory` | `react_parser`、`prompts`、各 `tools/*` |

不要为了「看起来像 OOP」给无状态逻辑套空类。

### 添加工具

1. 在 `my-agent/src/tools/` 新增模块，导出：
   - `NAME: str`
   - `DESCRIPTION: str`（注入 system prompt，写清输入格式与示例）
   - `run(input: str) -> str`
2. 在 `src/tools/__init__.py` 的 `TOOLS` 字典中注册。
3. 工具应返回可读字符串；异常在工具内转为错误信息，避免抛穿 Agent 循环。

### Agent 行为

- 解析格式固定：`Thought` / `Action` / `Action Input` 或 `Final Answer`（见 `prompts.py` 与 `react_parser.py`）。
- `MAX_ITERATIONS` 控制最大工具循环次数；改协议时同步改解析正则。
- `reset` 清空记忆；改持久化路径时同步改 `PersistentMemory`。

### 记忆

- `ConversationMemory`：内存历史 + 轮数裁剪。
- `PersistentMemory`：继承前者，每次 `add_message` / `clear` 落盘。
- 切换记忆实现时，改 `agent.py` 中的构造即可。

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
- 不要在未确认时改动 ReAct 输出协议格式（会破坏解析）。
- 不要把无状态工具再改回空壳类。

## 快速自检

- [ ] `pip install -r requirements.txt` 可安装
- [ ] 配置 `.env` 后 `cd my-agent && python main.py` 可启动
- [ ] 新工具已写入 `TOOLS` 且 `DESCRIPTION` 含输入示例
- [ ] 未改动 `.gitignore` 对密钥与缓存的保护
