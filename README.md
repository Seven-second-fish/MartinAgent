# MartinAgent

> **学习声明**：本项目仅用于学习与研究目的。请勿使用 AI 对本项目进行修改或自动改动。

基于 **ReAct**（Thought → Action → Observation）的命令行 AI Agent。  
支持 OpenAI 兼容 API（OpenAI / DeepSeek / 智谱等），可调用计算、文件、网页、时间、天气等工具完成任务。

[安装](#安装) · [使用](#使用) · [内置工具](#内置工具) · [项目结构](#项目结构)

---

## 安装

在仓库**根目录**操作：

```bash
cd my-agent
# 创建虚拟环境（强烈推荐，避免依赖冲突）
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# 安装核心依赖
pip install -r requirements.txt

# 验证安装
python -c "import openai; print('OpenAI SDK 安装成功')"

# 编辑 my-agent/.env，填入 API Key
cp my-agent/.env.example my-agent/.env

# 如果无法执行上面操作
# 退出虚拟环境
deactivate
# 删除损坏的虚拟环境目录
rm -rf ~/project/MartinAgent/.venv
# 重复上面的操作
```

### 配置（`my-agent/.env`）


| 变量                | 说明                                  |
| ----------------- | ----------------------------------- |
| `OPENAI_API_KEY`  | API 密钥                              |
| `OPENAI_BASE_URL` | Base URL（兼容 OpenAI 协议）              |
| `MODEL_NAME`      | 模型名，如 `deepseek-chat`、`gpt-4o-mini` |
| `DEFAULT_CITY`    | 天气默认城市（可选）                          |


最小示例（DeepSeek）：

```env
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
```

其他常用 Base URL：OpenAI `https://api.openai.com/v1`；智谱 `https://open.bigmodel.cn/api/paas/v4`。完整注释见 `.env.example`。

---



## 使用

```bash
cd my-agent
python main.py
```

启动后按轮输出思考过程（流式），最多约 5 轮工具调用。


| 输入      | 说明                                      |
| ------- | --------------------------------------- |
| 任务描述    | 开始执行                                    |
| `reset` | 清空对话记忆（若启用持久化，会同步清空 `logs/memory.json`） |
| `quit`  | 退出                                      |




### 记忆

- **默认**：进程内记忆（`ConversationMemory`），重启后丢失。
- **可选持久化**：在 `src/core/agent.py` 中改用 `PersistentMemory`，历史写入 `my-agent/logs/memory.json`，重启后自动加载。



### 示例

```text
帮我算一下 sqrt(144) + 3 * 5
现在几点了？上海天气怎么样？
把「hello」写入 notes.txt，再读出来
```

文件读写仅限 `my-agent/workspace/`。

---



## 内置工具


| 工具名           | 说明                   |
| ------------- | -------------------- |
| `calculator`  | 数学计算                 |
| `file_tool`   | 在 `workspace/` 内读写文件 |
| `web_tool`    | 获取网页纯文本              |
| `get_time`    | 当前时间                 |
| `get_weather` | 查询天气                 |
| `roll_dice`   | 掷塞子                 |


---



## 项目结构

```text
MartinAgent/
├── requirements.txt
├── AGENT.md                 # 给 AI / 开发者的约定
├── README.md
└── my-agent/
    ├── main.py              # 入口
    ├── .env.example
    ├── workspace/           # 文件沙箱
    ├── logs/                # 运行时记忆等（启用持久化时写入 memory.json）
    └── src/
        ├── core/            # Agent 与 LLM 客户端
        ├── tools/           # 工具
        └── memory/          # 对话记忆（内存 / 可选持久化）
```

---



## 注意

- 需要 Python 3.10+ 和可用的大模型 API Key
- 依赖主要是：`openai`、`python-dotenv`、`requests`、`colorama`

