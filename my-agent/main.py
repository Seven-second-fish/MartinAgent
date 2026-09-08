"""
AI Agent 入口文件
"""

from typing import Protocol

from src.core import ReActAgent, PlanAndSolveAgent, ReflectionAgent, AutoGenAgent, LangGraphAgent


class Agent(Protocol):
    """所有 agent 的最小接口：能接任务、能重置。"""

    def run(self, task: str) -> str: ...

    def reset(self) -> None: ...


# 模式注册表：加新 agent 只需在这里加一行，提示文字会自动跟着变
AGENTS = {
    # React: Thought (思考) Action (行动) Observation (观察)
    "1": ("react", ReActAgent),
    # Plan-and-Solve：Planner 规划步骤 → Executor 逐步执行
    "2": ("plan_and_solve", PlanAndSolveAgent),
    # Reflection: Execution 执行 -> Reflection 反思 -> Refinement 优化
    "3": ("reflection", ReflectionAgent),
    # AutoGen：多角色共享历史轮流对话（ProductManager→Engineer→CodeReviewer→UserProxy）
    "4": ("autogen", AutoGenAgent),
    # LangGraph: LangGraph 将智能体的执行流程建模为一种状态机（State Machine），
    # 并将其表示为有向图（Directed Graph）。在这种范式中，图的节点（Nodes）代表一个具体的计算步骤（如调用 LLM、执行工具），
    # 而边（Edges）则定义了从一个节点到另一个节点的跳转逻辑。
    "5": ("langgraph", LangGraphAgent),
}


def select_agent() -> Agent:
    """循环询问，直到输入有效模式。"""
    hint = "，".join(f"{key}：{name}" for key, (name, _) in AGENTS.items())
    while True:
        choice = input(f"请输入agent模式，{hint}：").strip()
        if choice in AGENTS:
            _, agent_cls = AGENTS[choice]
            return agent_cls()
        print("输入有误！请重新输入")

def run_repl(agent: Agent) -> None:
    """任务循环：quit 退出，reset 清空记忆，其余交给 agent。"""
    while True:
        try:
            task = input("\n📝 请输入任务：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 再见！")
            return

        if not task:
            continue

        if task.lower() == "quit":
            print("👋 再见！")
            return

        if task.lower() == "reset":
            agent.reset()
            continue

        try:
            # run() 内部已打印最终答案/兜底文案，返回值这里无需再展示
            agent.run(task)
        except KeyboardInterrupt:
            print("\n已中断当前任务，可以继续输入新任务。")
            agent.reset()  # 中断后模型思考到一半，对话状态可能不一致，建议清掉
        except Exception as e:
            print(f"\n⚠️ 执行出错：{e}")
            print("已回到输入状态，可继续使用（输入 reset 可清空上下文）。")


def main() -> None:
    agent = select_agent()
    print("=" * 60)
    print("🤖 AI Agent 已启动！输入 'quit' 退出，'reset' 重置对话")
    print("=" * 60)
    run_repl(agent)


if __name__ == "__main__":
    main()