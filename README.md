## 目录结构
my-agent/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent 核心逻辑
│   │   └── llm_client.py     # LLM 调用封装
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── calculator.py     # 计算器工具
│   │   ├── file_tool.py      # 文件读写工具
│   │   └── web_tool.py       # 网络请求工具
│   └── memory/
│       ├── __init__.py
│       └── conversation.py   # 对话记忆
├── tests/
├── logs/
├── .env                      # API Key 配置
└── main.py                   # 入口文件
