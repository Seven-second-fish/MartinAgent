"""第 2 课练习：验证工具 schema / 工具调用 / 记忆裁剪（迁移后版本）。

覆盖：
  1. build_tool_schemas()：7 个工具，schema 格式正确
  2. call_tool()：有参 / 无参 / 未知工具 / 异常工具
  3. ConversationMemory 按轮裁剪：tool 消息不产生孤儿

推荐在 my-agent/ 下运行：
  cd ~/project/MartinAgent/my-agent
  source agent-env/bin/activate
  python test/test1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把 my-agent/ 加入搜索路径（本文件在 test/ 里，上一级才是含 src 的目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.memory.conversation import ConversationMemory
from src.tools import TOOLS, build_tool_schemas, call_tool

# --- 1. 工具 schema ---
schemas = build_tool_schemas()
names = {s["function"]["name"] for s in schemas}
assert len(schemas) == len(TOOLS) == 7, (len(schemas), len(TOOLS))
assert names == set(TOOLS.keys()), names
for s in schemas:
    fn = s["function"]
    assert s["type"] == "function"
    assert fn["parameters"]["type"] == "object", fn["name"]
    assert fn["description"], fn["name"]
print("1) build_tool_schemas：7 个工具 schema 格式正确 ->", sorted(names))

# --- 2. 工具调用 ---
r = call_tool("calculator", {"expression": "2 + 3 * 4"})
assert "14" in r, r
print("2a) call_tool 有参:", r)

r = call_tool("get_time", {})
assert "当前时间" in r, r
print("2b) call_tool 无参:", r)

r = call_tool("no_such_tool", {})
assert "不存在" in r and "calculator" in r, r
print("2c) call_tool 未知工具:", r)


# --- 3. 记忆按轮裁剪 ---
class BoomTool:
    def run(self, _: str = "") -> str:
        raise RuntimeError("boom")


TOOLS["boom_tool"] = BoomTool()
r = call_tool("boom_tool", {})
assert "工具执行异常" in r, r
del TOOLS["boom_tool"]
print("2d) call_tool 异常:", r)

mem = ConversationMemory(max_turns=2, system_prompt="sys")
# 第 1 轮：user → assistant(tool_calls) → tool
mem.add_message("user", "算一下")
mem.add_message("assistant", "", tool_calls=[{"id": "c1", "type": "function",
                                              "function": {"name": "calculator", "arguments": "{}"}}])
mem.add_message("tool", "结果=4", tool_call_id="c1")
mem.add_message("assistant", "答案是 4")
# 第 2 轮：user → assistant
mem.add_message("user", "再算一次")
mem.add_message("assistant", "也是 4")
# 第 3 轮开始：user（触发裁剪，应裁掉第 1 轮整轮，不留孤儿 tool 消息）
mem.add_message("user", "继续")

roles = [m["role"] for m in mem.get_messages()]
assert roles == ["system", "user", "assistant", "user"], roles
assert not any(m["role"] == "tool" for m in mem.get_messages()), "tool 消息不应成为孤儿"
print("3) 记忆按轮裁剪：完整轮被裁掉，无孤儿 tool 消息 ->", roles)

print("\n✅ 全部断言通过")
