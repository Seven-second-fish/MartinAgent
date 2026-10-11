"""
martin_agent 包根：MartinAgent 的全部实现代码。

子包：
  - core/    各 agent 实现、LLM 客户端、提示词
  - tools/   无状态工具模块
  - memory/  对话记忆与轨迹记忆

本文件刻意不做任何导入，避免 `import martin_agent.memory` 之类触发无关模块（如 openai）加载。
项目级路径与 .env 统一见 martin_agent/paths.py。
"""
