"""
AI Agent 入口文件
"""

from typing import Protocol

from martin_agent import core
from martin_agent.paths import ensure_runtime_dirs


class Agent(Protocol):
    """所有 agent 的最小接口：能接任务、能重置。"""

    def run(self, task: str) -> str: ...

    def reset(self) -> None: ...


# 模式注册表：加新 agent 只需在这里加一行，提示文字会自动跟着变。
# 值写成（显示名，core 包中的类名）：实例化时才从 core 取属性，
# 因此模式 5 的可选依赖没装时，也只会在真的选中它的时候才提示。
AGENTS = {
    # React: Thought (思考) Action (行动) Observation (观察)
    "1": ("react", "ReActAgent"),
    # Plan-and-Solve：Planner 规划步骤 → Executor 逐步执行
    "2": ("plan_and_solve", "PlanAndSolveAgent"),
    # Reflection: Execution 执行 -> Reflection 反思 -> Refinement 优化
    "3": ("reflection", "ReflectionAgent"),
    # AutoGen：多角色共享历史轮流对话（ProductManager→Engineer→CodeReviewer→UserProxy）
    "4": ("autogen", "AutoGenAgent"),
    # LangGraph: LangGraph 将智能体的执行流程建模为一种状态机（State Machine），
    # 并将其表示为有向图（Directed Graph）。在这种范式中，图的节点（Nodes）代表一个具体的计算步骤（如调用 LLM、执行工具），
    # 而边（Edges）则定义了从一个节点到另一个节点的跳转逻辑。
    # 需要可选依赖，未安装时选中本模式会得到安装提示：pip install -e ".[langgraph]"
    "5": ("langgraph", "LangGraphAgent"),
}


def _resolve_agent_class(choice: str):
    """把模式编号解析为 agent 类（模式 5 会在此时才触发可选依赖导入）。"""
    _, attr_name = AGENTS[choice]
    return getattr(core, attr_name)


def select_agent() -> Agent:
    """循环询问，直到成功实例化一个 agent；可选依赖缺失时提示后重新选择。"""
    hint = "，".join(f"{key}：{name}" for key, (name, _) in AGENTS.items())
    while True:
        try:
            choice = input(f"请输入agent模式，{hint}：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 再见！")
            raise SystemExit(0) from None

        if choice not in AGENTS:
            print("输入有误！请重新输入")
            continue

        try:
            agent_cls = _resolve_agent_class(choice)
        except ModuleNotFoundError as e:
            # 典型情况：选了模式 5 但没装 langgraph。回到选择，不要把程序带崩。
            print(f"\n⚠️ 该模式当前不可用：{e}\n")
            continue

        return agent_cls()


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
    ensure_runtime_dirs()  # 预建 logs/ workspace/ generated/
    try:
        agent = select_agent()
    except RuntimeError as e:
        # 典型情况：.env 未配置 API Key
        print(f"\n⚠️ 启动失败：{e}")
        return
    print("=" * 60)
    print("🤖 AI Agent 已启动！输入 'quit' 退出，'reset' 重置对话")
    print("=" * 60)
    run_repl(agent)


if __name__ == "__main__":
    main()