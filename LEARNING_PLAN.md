# MartinAgent 学习计划

用「做一个能跑的 Agent」来学 Agent。  
本文只写**要做什么功能**和一点点提示；具体语法/API 请自己浏览器搜教程实现。

你的背景假设：

- Python 基础几乎为 0 → 先能读懂本仓库，再改、再加
- Linux 用过约 3 年 → 环境/路径/权限自己能搞定；命令忘了就 `man` 或搜

当前仓库**已经具备**的能力（对照用，不必重做）：

- 终端入口 + 三种 agent（ReAct / Plan-and-Solve / Reflection）
- OpenAI 兼容 LLM 调用（含流式）
- 工具：计算、文件沙箱、网页、时间、天气
- 对话记忆（内存 / 可选持久化）
- 原生函数调用（`tools` 字段）统一承载工具调用与结构化输出（无正则解析层）

建议顺序：**能跑通 → 读懂 → 小改 → 新功能 → 加深 Agent 能力**。  
每一阶段结束时，用自己的话写 3～5 行笔记：「这个功能解决什么问题」。

---

## 阶段 0：把现有项目跑起来

**目标**：你能独立启动、提问、看到工具被调用。

| 要做的事 | 小提示 |
|----------|--------|
| 创建/激活 Python 虚拟环境 | 搜：`python venv 是什么`、`source activate` |
| 用 pip 安装 `requirements.txt` | 搜：`pip install -r` |
| 配置 `.env` 里的 API Key | 搜：`dotenv 环境变量`；密钥不要提交 Git |
| 运行 `python main.py`，试 3 个示例任务 | 看终端里有没有 `Action` / 工具返回 |
| 会用 `reset` / `quit` | 对照 `main.py` 里的分支 |

**过关**：不靠别人口述，你能从「打开终端」到「算出一道题 + 查一次天气」。

---

## 阶段 1：Python 最小集（只服务本项目）

**目标**：能读懂 `my-agent/src` 里的代码在干什么（不要求一次学会全部 Python）。

按文件读，边读边搜；每项只需会「本项目用到的那一点」。

| 要搞懂的点 | 对照本仓库 | 小提示（搜什么） |
|------------|------------|------------------|
| 脚本入口、`import`、包路径 | `main.py`、`from src.xxx` | `python 模块 import`、`__init__.py` |
| 函数 / 返回值 / 字符串 | 各 `tools/*.py` 的 `run()` | `python def`、`f-string` |
| 字典、列表 | `agent` 里 `tools`、记忆里的 messages | `python dict list` |
| 类：何时有状态 | `ReActAgent`、`LLMClient`、Memory | `python class self`；对比工具为何不用类 |
| 读写文件、异常 | `file_tool`、`persistentmemory` | `python open encoding`、`try except` |
| 正则简单用法 | `reflection_agent._strip_code_fences`（仅剩的用法：剥代码围栏） | `python re.search`；先看懂，不急着写复杂正则 |
| HTTP 请求 | `web_tool`、`weather` | `python requests get` |
| 环境变量 | `llm_client`、天气默认城市 | `os.getenv`、`python-dotenv` |

**过关**：能指着 `agent.py` 的 `run()` 讲清楚：一轮里先干什么、后干什么。

---

## 阶段 2：吃透 ReAct（在现有代码上「小手术」）

**目标**：理解 Agent「为什么要循环」，而不是只会调 API。

| 要做的功能 / 改动 | 小提示 |
|-------------------|--------|
| 画一张自己的流程图：用户输入 → LLM → 工具调用 → 记忆 → 下一轮 | 对照 `react_agent.py` |
| 把 `MAX_ITERATIONS` 改成可配置（如读环境变量） | 搜：`python 读环境变量 int` |
| 给解析失败时的提示文案改成你自己的版本 | 只改字符串，观察模型是否更容易纠正 |
| 强制走工具：故意问计算题，确认它不会心算 | 对照 system prompt 里的规则 |
| 观察模型空回复时 agent 如何提示重试 | `react_agent.py` 分支 2 |

**过关**：能解释 `action` / `final_answer` / `unknown` 三种结果各自通向哪段代码。

---

## 阶段 3：工具系统（最适合练手）

**目标**：独立加一个新工具，并让 Agent 真的会调用它。

约定回顾：工具是**无状态模块**，导出 `NAME` / `DESCRIPTION` / `run()`，再在 `TOOLS` 注册。

| 要做的功能 | 小提示 |
|------------|--------|
| 新工具：随机数 / 掷骰子 | 搜：`python random`；DESCRIPTION 写清输入格式 |
| 新工具：简易待办（读写 `workspace/todo.txt`） | 复用文件沙箱思路；注意路径不要逃出 `workspace` |
| 新工具：翻译或摘要（仍走 LLM，或调免费 API） | 搜：`openai chat completions`；注意和「主循环 LLM」别搅乱 |
| 给某个工具加超时 / 更友好的错误信息 | 搜：`requests timeout`、异常信息怎么返回字符串 |
| （可选）给工具写 `__main__` 自测 | 不启动 Agent 也能 `python -m` 测工具 |

**过关**：新工具不改 Agent 主循环逻辑（只改 tools + 注册表）就能被模型调用。

---

## 阶段 4：记忆与上下文

**目标**：搞清「Agent 记得什么、为什么会忘、为什么会乱」。

| 要做的功能 | 小提示 |
|------------|--------|
| 默认改用 `PersistentMemory`，验证重启后续聊 | 对照 `agent.py` 注释切换；看 `logs/memory.json` |
| 限制历史长度：改 `max_turns`，观察长对话变化 | 搜：`上下文窗口 context window`（概念） |
| 增加「只保留最近 N 轮 + 始终保留 system」的裁剪策略 | 读 `conversation.py` 现有裁剪再改 |
| （进阶）对话摘要：超长时让模型总结旧历史再塞回 | 搜：`conversation summary memory` |
| （进阶）按「用户偏好」单独存一小段长期记忆 | 例如喜欢的城市、称呼；可用另一个 json |

**过关**：能说清「工具 Observation 为什么要写回 messages」。

---

## 阶段 5：解析与可靠性

**目标**：模型输出不听话时，你有办法兜住。

| 要做的功能 | 小提示 |
|------------|--------|
| 统计解析失败次数，打印简单计数 | 变量累加即可 |
| 支持模型用中文标签（如「最终答案：」） | 在 parser 里加一种别名匹配 |
| 非法工具名时，把可用工具列表写进 Observation | Agent 里已有类似逻辑，可加强 |
| ~~（进阶）用 JSON 模式输出 Action~~ | ✅ 已完成：Planner / Reflection 改用 `submit_plan` / `submit_review` 函数调用提交参数表 |
| （进阶）加 2～3 个解析单测 | 搜：`pytest 入门`；输入样本文本 → 断言 type |

**过关**：准备 5 段「故意歪」的模型输出，你的 parser 行为符合预期。

---

## 阶段 6：交互与工程化（Linux 你更熟，可加速）

**目标**：项目用起来像「自己的小工具」，而不是演示脚本。

| 要做的功能 | 小提示 |
|------------|--------|
| 命令行参数：`--task` 直接跑一次就退出 | 搜：`argparse` |
| 日志：把每轮 Thought/Action 追加到 `logs/run.log` | 搜：`python logging` 或简单 `open append` |
| 更清晰的颜色/无颜色开关 | 已有 colorama；搜：`NO_COLOR` 惯例 |
| 补全 README 里「如何新加工具」一小节 | 用你自己的话写，给未来的自己看 |
| Git：合理 `.gitignore`、小步提交 | 你已有基础；搜：`git commit 最佳实践`（别提交 `.env`） |

**过关**：别人按 README 能跑；你按自己的笔记能加工具。

---

## 阶段 7：Agent 能力升级（选修，按兴趣选 2～3 个）

这些会明显超出当前脚手架，但最接近「真·Agent 学习」。

| 方向 | 要做的功能 | 小提示 |
|------|------------|--------|
| 多步规划 | 先让模型输出计划列表，再逐步执行 | 搜：`plan and execute agent` |
| ~~官方 Tool Calling~~ | ✅ 已完成：三个 agent 全部走 API `tools` 字段；`llm_client.chat_stream` 组装流式 tool_calls | 搜：`openai function calling` / `tool calls` |
| 检索增强（RAG 迷你版） | 把 `workspace` 文档切块检索后再回答 | 搜：`简易 RAG python`；先别上向量库也行 |
| 人机确认 | 危险操作（删文件、外网 POST）先 `input` 确认 | 搜：`human in the loop agent` |
| 简单 Web UI | 用 Streamlit/Gradio 包一层对话框 | 搜：`streamlit chat` |
| 评测 | 固定 10 个任务脚本，自动跑并记录是否调用对工具 | 自己定成功标准即可 |

**过关**：任选一条做成「可演示」的小功能，并写清它比纯 ReAct 文本协议好在哪、差在哪。

---

## 建议的每周节奏（可改）

| 周 | 焦点 |
|----|------|
| 第 1 周 | 阶段 0 + 阶段 1（跑通 + 读懂主循环） |
| 第 2 周 | 阶段 2 + 阶段 3（小改 ReAct + 至少 1 个新工具） |
| 第 3 周 | 阶段 4 + 阶段 5（记忆 + 解析） |
| 第 4 周 | 阶段 6 + 阶段 7 选 1（工程化 + 一个升级点） |

每天有代码改动就提交一次；提交说明写「做了什么功能」，方便回顾。

---

## 学习时怎么搜更省事

1. 先写清目标：「我要让 Agent 多一个掷骰子工具」
2. 再拆成关键词：`python random`、`模块导出函数`、`注册到字典`
3. 先看官方文档 / 短教程，再抄进本项目风格（本仓库工具是模块不是类）
4. 卡住超过 30 分钟：把报错全文、相关文件路径记下来再问人或 AI

Linux 命令不熟时：先 `pwd` / `ls` / `cd` 定位，再搜具体命令；不必提前背完整手册。

---

## 不要过早做的事

- 一上来上 LangChain / 复杂框架（先把本仓库主循环吃透）
- 一上来向量数据库、多 Agent 协作
- 为了「架构漂亮」大重构（功能驱动小步改）
- 把 API Key 写进代码或提交到 Git

---

## 和本仓库文档的关系

| 文档 | 用途 |
|------|------|
| `README.md` | 怎么安装、怎么跑 |
| `AGENT.md` | 改代码时的约定（类 vs 模块、怎么加工具） |
| 本文 `LEARNING_PLAN.md` | 你学 Agent 时「下一步做什么功能」 |

读代码顺序建议：`main.py` → `react_agent.py` → `llm_client.py`（重点看流式 tool_calls 组装）→ 某一个 `tools/*.py` → `memory/*`。
