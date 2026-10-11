"""工具注册表与对话记忆的行为测试。

覆盖：
  1. build_tool_schemas()：工具数量与 schema 格式
  2. call_tool()：有参 / 无参 / 未知工具 / 异常工具
  3. ConversationMemory 按轮裁剪：tool 消息不产生孤儿
"""

from __future__ import annotations

from martin_agent.memory.conversation import ConversationMemory
from martin_agent.tools import TOOLS, build_tool_schemas, call_tool


def test_build_tool_schemas_format():
    """每个注册工具都生成合法的 OpenAI function schema。"""
    schemas = build_tool_schemas()
    names = {s["function"]["name"] for s in schemas}

    assert len(schemas) == len(TOOLS) == 7, (len(schemas), len(TOOLS))
    assert names == set(TOOLS.keys()), names
    for schema in schemas:
        fn = schema["function"]
        assert schema["type"] == "function"
        assert fn["parameters"]["type"] == "object", fn["name"]
        assert fn["description"], fn["name"]


def test_call_tool_with_argument():
    assert "14" in call_tool("calculator", {"expression": "2 + 3 * 4"})


def test_call_tool_without_argument():
    assert "当前时间" in call_tool("get_time", {})


def test_call_tool_unknown_name():
    result = call_tool("no_such_tool", {})
    assert "不存在" in result and "calculator" in result


def test_call_tool_exception_is_caught():
    """工具内部异常必须转成错误字符串，不能抛穿 Agent 循环。"""

    class BoomTool:
        def run(self, _: str = "") -> str:
            raise RuntimeError("boom")

    TOOLS["boom_tool"] = BoomTool()  # type: ignore[assignment]
    try:
        result = call_tool("boom_tool", {})
    finally:
        del TOOLS["boom_tool"]
    assert "工具执行异常" in result


def test_memory_trims_by_turn_without_orphan_tool_messages():
    mem = ConversationMemory(max_turns=2, system_prompt="sys")
    # 第 1 轮：user → assistant(tool_calls) → tool
    mem.add_message("user", "算一下")
    mem.add_message(
        "assistant",
        "",
        tool_calls=[
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "calculator", "arguments": "{}"},
            }
        ],
    )
    mem.add_message("tool", "结果=4", tool_call_id="c1")
    mem.add_message("assistant", "答案是 4")
    # 第 2 轮：user → assistant
    mem.add_message("user", "再算一次")
    mem.add_message("assistant", "也是 4")
    # 第 3 轮开始：user（触发裁剪，应裁掉第 1 轮整轮）
    mem.add_message("user", "继续")

    messages = mem.get_messages()
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert not any(m["role"] == "tool" for m in messages), "tool 消息不应成为孤儿"


def test_file_tool_stays_inside_workspace():
    """沙箱边界：路径穿越必须被拒绝，正常读写落在 <repo>/workspace。"""
    from martin_agent.paths import WORKSPACE_DIR
    from martin_agent.tools import file_tool

    assert file_tool.ALLOWED_DIR == WORKSPACE_DIR
    assert "不允许" in file_tool.run("read:../../main.py")
    assert "不允许" in file_tool.run("write:../escape.txt:x")

    written = file_tool.run("write:unit_test_tmp.txt:hello")
    assert "成功写入文件" in written
    assert "hello" in file_tool.run("read:unit_test_tmp.txt")
    (WORKSPACE_DIR / "unit_test_tmp.txt").unlink(missing_ok=True)
