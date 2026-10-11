"""流式工具调用组装测试：mock OpenAI 流，验证 ChatResult 组装与 token 累积。

覆盖：
  1. 内容分片 + tool_calls 分片（arguments 跨多个 chunk）→ 正确组装
  2. 工具参数 JSON 解析失败 → arguments={}
  3. usage 累积
  4. 纯文本流（无工具调用）

LLMClient 构造时会读 OPENAI_API_KEY，这里在导入前塞占位值，
测试全程 mock SDK，不会发出任何真实请求。
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from martin_agent.core.llm_client import LLMClient, ToolCall  # noqa: E402


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


def run_stream_case(chunks, expect_content, expect_tool_calls, expect_tokens):
    client = LLMClient()
    client.client.chat.completions.create = lambda **kw: fake_stream(chunks)
    result = client.chat_stream([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert result.content == expect_content, (result.content, expect_content)
    assert result.tool_calls == expect_tool_calls, (result.tool_calls, expect_tool_calls)
    assert client.total_tokens == expect_tokens, (client.total_tokens, expect_tokens)


def test_content_and_tool_call_chunks_are_assembled():
    run_stream_case(
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


def test_broken_tool_arguments_fall_back_to_empty_dict():
    run_stream_case(
        [
            make_chunk(tool_calls=[make_tc_delta(0, tc_id="call_2", name="calculator", args='{"expr')]),
            make_chunk(finish_reason="tool_calls"),
            make_chunk(usage=SimpleNamespace(total_tokens=10)),
        ],
        expect_content="",
        expect_tool_calls=[ToolCall(id="call_2", name="calculator", arguments={})],
        expect_tokens=10,
    )


def test_plain_text_stream_has_no_tool_calls():
    run_stream_case(
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
