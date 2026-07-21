"""
AI Agent 入口文件
"""

from src.core import ReActAgent

def main():
    agent = ReActAgent()

    print("=" * 60)
    print("🤖 AI Agent 已启动！输入 'quit' 退出，'reset' 重置对话")
    print("=" * 60)

    while True:
        try:
            task = input("\n📝 请输入任务：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 再见！")
            break

        if not task:
            continue

        if task.lower() == "quit":
            print("👋 再见！")
            break

        if task.lower() == "reset":
            agent.reset()
            continue

        # 执行任务
        agent.run(task)

if __name__ == "__main__":
    main()