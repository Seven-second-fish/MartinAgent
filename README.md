# MartinAgent

基于 **ReAct**（Reasoning + Acting）范式的命令行 AI Agent。通过 Thought → Action → Observation 循环调用工具完成任务，支持 OpenAI 兼容 API（OpenAI / DeepSeek / 智谱等），并可将对话历史持久化到本地。

## 功能

- ReAct 多轮推理与工具调用（最大迭代次数可配置）
- 流式输出 LLM 回复，并统计 Token 消耗
- 持久化对话记忆（重启后仍可延续上下文）
- 内置工具：计算器、文件读写、网页抓取、时间、天气

## 环境要求

- Python 3.10+
- 可用的大模型 API Key（OpenAI 兼容接口）

## 快速开始

```bash
# 1. 克隆仓库后进入项目根目录
cd MartinAgent

# 2. 创建并激活虚拟环境
python3 -m venv agent-env
source agent-env/bin/activate   # Windows: agent-env\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp my-agent/.env.example my-agent/.env
# 编辑 my-agent/.env，填入你的 API Key 与模型配置

# 5. 启动 Agent
cd my-agent
python main.py
```

启动后可输入任务；输入 `reset` 清空对话记忆，输入 `quit` 退出。

## 配置说明

在 `my-agent/.env` 中配置（参考 `.env.example`）：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API 密钥 |
| `OPENAI_BASE_URL` | API Base URL（兼容 OpenAI 协议） |
| `MODEL_NAME` | 模型名称，如 `deepseek-chat`、`gpt-4o-mini` |
| `DEFAULT_CITY` | 天气查询默认城市（可选） |

## 内置工具

| 工具名 | 说明 |
|--------|------|
| `calculator` | 安全数学计算（加减乘除、开方、三角函数等） |
| `file_tool` | 在 `./workspace` 沙箱内读写文件 |
| `web_tool` | 获取指定 URL 的网页纯文本（截断前 2000 字符） |
| `get_time` | 获取当前本地日期时间 |
| `get_weather` | 查询城市或当前位置天气（wttr.in） |

## 目录结构

```text
MartinAgent/
├── README.md
├── requirements.txt
├── .gitignore
├── agent-env/                 # 本地虚拟环境（勿提交）
└── my-agent/
    ├── main.py                # 入口
    ├── .env.example           # 环境变量模板
    ├── .env                   # 本地密钥（勿提交）
    ├── logs/                  # 运行时日志与记忆文件
    ├── workspace/             # file_tool 沙箱目录
    ├── tests/
    └── src/
        ├── core/
        │   ├── agent.py       # ReAct Agent 核心
        │   └── llm_client.py  # LLM 调用封装
        ├── tools/
        │   ├── calculator.py
        │   ├── file_tool.py
        │   ├── web_tool.py
        │   ├── time.py
        │   └── weather.py
        └── memory/
            ├── conversation.py
            └── persistentmemory.py
```

## 使用示例

```text
📝 请输入任务：帮我算一下 sqrt(144) + 3 * 5
📝 请输入任务：现在几点了？上海天气怎么样？
📝 请输入任务：把「hello」写入 notes.txt，再读出来
```

文件读写仅限 `my-agent/workspace/` 目录，例如：`write:notes.txt:hello`。

## 注意事项

- **不要将 `.env` 提交到 Git**；仓库中已提供 `.env.example` 作为模板。
- 若 API Key 曾被提交到版本库，请尽快在服务商控制台轮换密钥。
- `file_tool` 仅允许操作 `workspace/`，请勿依赖其处理敏感路径外的文件。
