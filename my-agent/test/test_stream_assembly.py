"""流式工具调用组装测试：mock OpenAI 流，验证 ChatResult 组装与 token 累积。

覆盖：
  1. 内容分片 + tool_calls 分片（arguments 跨多个 chunk）→ 正确组装
  2. 工具参数 JSON 解析失败 → arguments={}
  3. usage 累积

推荐在 my-agent/ 下运行：
  cd ~/project/MartinAgent/my-agent
  python test/test_stream_assembly.py
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

# 把 my-agent/ 加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.llm_client import LLMClient, ToolCall


def make_chunk(content=None, tool_calls=None, finish_reason=None, usage=None):
    """构造一个与 openai 流 chunk 结构一致的 SimpleNamespace。"""
    delta = {"content": content, "tool_calls": tool_calls}
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(**delta), finish_reason=finish_reason)],
        usage=usage,
    )


def make_tc_delta(index, tc_id=None, name=None, args=None):
    return SimpleNamespace(
        index=index,
        id=tc_id,
        function=SimpleNamespace(name=name, arguments=args),
    )


def fake_stream(chunks):
    """把 chunk 列表变成生成器，模拟 SDK 的流式迭代。"""
    yield from chunks


def run_stream_test(client, chunks, expect_content, expect_tool_calls, expect_tokens):
    client.client.chat.completions.create = lambda **kw: fake_stream(chunks)
    result = client.chat_stream([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert result.content == expect_content, (result.content, expect_content)
    assert result.tool_calls == expect_tool_calls, (result.tool_calls, expect_tool_calls)
    assert client.total_tokens == expect_tokens, (client.total_tokens, expect_tokens)
    print(f"   ✅ content={result.content!r} tool_calls={result.tool_calls!r} tokens={client.total_tokens}")


# 1) 正常流：内容分片 + 工具参数跨 chunk 分片
client = LLMClient()
run_stream_test(
    client,
    [
        make_chunk(content="我来"),
        make_chunk(content="计算："),
        make_chunk(tool_calls=[make_tc_delta(0, tc_id="call_1", name="calculator", args='{"expre')]),
        make_chunk(tool_calls=[make_tc_delta(0, args='ssion": "2+3"}')]),
        make_chunk(finish_reason="tool_calls"),
        make_chunk(usage=SimpleNamespace(total_tokens=42)),
    ],
    expect_content="我来计算：",
    expect_tool_calls=[ToolCall(id="call_1", name="calculator", arguments={"expression": "2+3"})],
    expect_tokens=42,
)

# 2) 工具参数残缺（JSON 解析失败）→ arguments={}
client2 = LLMClient()
run_stream_test(
    client2,
    [
        make_chunk(tool_calls=[make_tc_delta(0, tc_id="call_2", name="calculator", args='{"expr')]),
        make_chunk(finish_reason="tool_calls"),
        make_chunk(usage=SimpleNamespace(total_tokens=10)),
    ],
    expect_content="",
    expect_tool_calls=[ToolCall(id="call_2", name="calculator", arguments={})],
    expect_tokens=10,
)

# 3) 纯文本流（无工具调用）
client3 = LLMClient()
run_stream_test(
    client3,
    [
        make_chunk(content="你好"),
        make_chunk(content="，世界"),
        make_chunk(finish_reason="stop"),
        make_chunk(usage=SimpleNamespace(total_tokens=7)),
    ],
    expect_content="你好，世界",
    expect_tool_calls=[],
    expect_tokens=7,
)

print("\n✅ 流式组装全部通过")
