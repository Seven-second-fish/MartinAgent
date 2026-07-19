"""
ReAct Agent 核心实现
思路：Thought（思考）→ Action（行动）→ Observation（观察）→ 循环
"""

import re
import json
from colorama import Fore, Style, init

from src.core.llm_client import LLMClient
from src.memory.persistentmemory import PersistentMemory
from src.tools.calculator import CalculatorTool
from src.tools.file_tool import FileTool
from src.tools.web_tool import WebTool
from src.tools.time import TimeTool
from src.tools.weather import WeatherTool

# 初始化色彩输出
init(autoreset=True)

# 系统提示词
SYSTEM_PROMPT = """你是一个智能任务助手，能够通过调用工具来完成用户交给你的任务。

## 你拥有以下工具：

{tool_descriptions}

## 工作流程（严格遵守）：

每次回复必须按照以下格式，直到任务完成：
Thought: [分析当前情况，思考下一步该做什么]
Action: [工具名称]
Action Input: [工具的输入参数]

当工具返回结果后，你会收到：
Observation: [工具返回的结果]

然后继续思考，直到任务完成，最后输出：
Thought: [最终思考，确认任务已完成]
Final Answer: [给用户的最终回答]

## 重要规则：
1. 每次只能调用一个工具
2. 如果不需要工具，直接输出 Final Answer
3. 遇到计算问题，必须使用 calculator 工具，不要自己心算
4. Action 字段只能填写工具名称，不能有其他内容
5. 如果工具返回错误，分析原因并尝试修正后重试
"""

class ReActAgent:
    """
    基于 ReAct 范式的 AI Agent
    
    ReAct = Reasoning（推理）+ Acting（行动）
    核心循环：Thought → Action → Observation → Thought → ...
    """

    MAX_ITERATIONS = 5 # 最大迭代次数

    def __init__(self):
        self.tools = {
            "calculator": CalculatorTool(),
            "file_tool": FileTool(),
            "web_tool": WebTool(),
            "get_time": TimeTool(),
            "get_weather": WeatherTool(),
        }
        

        # 构建工具描述（注入system prompt）
        tool_descriptions = "\n".join(
            f"- **{name}**：{tool.description}"
            for name, tool in self.tools.items()
        )
        self.llm = LLMClient()

        # 内存记忆写法，让 Agent 在重启后不能记住之前的对话
        # self.memory = ConversationMemory(
        #     max_turns=20,
        #     system_prompt=SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions),
        # )

        # 持久化记忆写法，让 Agent 在重启后还能记住之前的对话
        self.memory = PersistentMemory(
            save_path="./logs/memory.json",
            max_turns=20,
            system_prompt=SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions),
        )
        

    def run(self, task: str) -> str:
        """
        运行 Agent 处理任务
        
        Args:
            task: 用户任务描述
            
        Returns:
            Agent 最终回复
        """

        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"🤖 任务开始：{task}")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        self.memory.add_message("user", task)

        for i in range(1, self.MAX_ITERATIONS + 1):
            print(f"{Fore.YELLOW}---第{i}轮思考---{Style.RESET_ALL}")

            print(f"{Fore.GREEN}LLM 输出：{Style.RESET_ALL}")
            response = self.llm.chat_stream(self.memory.get_messages())
            print()

            # 解析LLM输出
            parsed = self._parse_response(response)

            # 情况一：任务完成，返回最终答案
            if parsed["type"] == "final_answer":
                self.memory.add_message("assistant", response)
                final = parsed["content"]
                print(f"\n{Fore.CYAN}{'='*60}")
                print(f"✅ 任务完成！")
                print(f"最终答案：{final}")
                print(f"Token 消耗：{self.llm.get_token_usage()}")
                print(f"{'='*60}{Style.RESET_ALL}\n")
                return final

            # 情况二：需要调用工具
            elif parsed["type"] == "action":
                tool_name = parsed["tool"]
                tool_input = parsed["input"]

                print(f"{Fore.MAGENTA}🔧 调用工具：{tool_name}")
                print(f"   输入：{tool_input}{Style.RESET_ALL}")

                # 执行工具
                observation = self._execute_tool(tool_name, tool_input)
                print(f"{Fore.BLUE}📋 工具返回：{observation}{Style.RESET_ALL}\n")

                # 将 LLM 输出和工具结果都加入记忆
                self.memory.add_message("assistant", response)
                self.memory.add_message(
                    "user", f"Observation: {observation}"
                )

            # 情况三：解析失败，提示 LLM 修正格式
            else:
                print(f"{Fore.RED}⚠️  输出格式解析失败，提示 LLM 修正{Style.RESET_ALL}")
                self.memory.add_message("assistant", response)
                self.memory.add_message(
                    "user",
                    "你的输出格式不正确。请严格按照 Thought/Action/Action Input 或 Final Answer 格式回复。",
                )
        # 超出最大迭代次数
        return "任务未能在规定步骤内完成，请尝试简化任务描述。"
    
    def _parse_response(self, response: str) -> dict:
        """
        解析 LLM 的输出，提取 Action 或 Final Answer
        
        Returns:
            {"type": "action", "tool": "...", "input": "..."}
            {"type": "final_answer", "content": "..."}
            {"type": "unknown"}
        """
        # 检查是否有 Final Answer
        final_match = re.search(
            r"Final Answer:\s*(.+?)(?:\n|$)", response, re.DOTALL
        )
        if final_match:
            return {"type": "final_answer", "content": final_match.group(1).strip()}

        # 检查是否有 Action
        action_match = re.search(r"Action:\s*(\w+)", response)
        input_match = re.search(
            r"Action Input:\s*(.+?)(?:\nThought|\nAction|\nObservation|$)",
            response,
            re.DOTALL,
        )

        if action_match and input_match:
            return {
                "type": "action",
                "tool": action_match.group(1).strip(),
                "input": input_match.group(1).strip(),
            }

        return {"type": "unknown"}

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """
        执行指定工具
        
        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            available = ", ".join(self.tools.keys())
            return f"错误：工具 '{tool_name}' 不存在。可用工具：{available}"

        try:
            return self.tools[tool_name].run(tool_input)
        except Exception as e:
            return f"工具执行异常：{str(e)}"

    def reset(self):
        """重置 Agent 状态（清空对话历史）"""
        self.memory.clear()
        print("Agent 状态已重置")

