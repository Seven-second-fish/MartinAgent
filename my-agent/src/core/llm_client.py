"""
LLM 客户端封装
统一管理大模型调用，支持多种 API 提供商

返回结构化结果（ChatResult）：
  - content：模型回复的文本内容
  - tool_calls：模型发起的工具调用（原生函数调用，无需正则解析）
  - finish_reason：结束原因（如 "stop" / "tool_calls"）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class ToolCall:
    """一次工具调用：名称 + 已解析为 dict 的参数。"""

    id: str
    name: str
    arguments: dict


@dataclass
class ChatResult:
    """一次 LLM 调用的结构化返回。"""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None


class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        self.model = os.getenv("MODEL_NAME")
        # prompt_tokens:输入测token
        # completion_tokens:输出测token
        # total_tokens = prompt_tokens + completion_tokens
        # 统计的是从启动main.py到调用完LLMClient.chat_stream()为止的token消耗
        self.total_tokens = 0

    def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        tools: list | None = None,
    ) -> ChatResult:
        """
        非流式对话请求。

        Args:
            messages: 对话历史，格式为 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数，越高越随机（0~2）
            tools: OpenAI tools 字段（原生函数调用）

        Returns:
            ChatResult
        """
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )

        if response.usage is not None:
            self.total_tokens += response.usage.total_tokens

        msg = response.choices[0].message
        tool_calls = []
        for tc in msg.tool_calls or []:
            raw = tc.function.arguments or ""
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_parse_arguments(raw),
                )
            )
        return ChatResult(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
        )

    def chat_stream(
        self,
        messages: list,
        temperature: float = 0.7,
        tools: list | None = None,
    ) -> ChatResult:
        """
        流式对话，边接收边打印，返回完整回复文本。

        工具调用在流中按 index 分片到达（id/name/arguments 增量），
        内容增量照旧实时打印；工具调用摘要只能在流结束后打印。
        """
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
            # 流式默认不带 usage；打开后会在最后一个 chunk 里附带整次请求的 token 统计
            stream_options={"include_usage": True},
            **kwargs,
        )

        full_response = ""
        finish_reason = None
        # 工具调用分片归并：index -> {"id": str, "name": str, "args": [分片]}
        acc: dict[int, dict] = {}
        for chunk in stream:
            # 累加usage；末尾 usage chunk 的 choices 常为空，必须先判空再读 delta
            if chunk.usage is not None:
                self.total_tokens += chunk.usage.total_tokens
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason is not None:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta.content:
                print(delta.content, end="", flush=True)
                full_response += delta.content
            for tc in delta.tool_calls or []:
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "args": []})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function.arguments:
                        slot["args"].append(tc.function.arguments)
        print()

        tool_calls = []
        for idx in sorted(acc):
            slot = acc[idx]
            raw = "".join(slot["args"])
            arguments = _parse_arguments(raw, show_warning=True)
            tool_calls.append(
                ToolCall(id=slot["id"], name=slot["name"], arguments=arguments)
            )
            print(f"🔧 工具调用：{slot['name']}({arguments})")

        return ChatResult(
            content=full_response,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

    def get_token_usage(self) -> dict:
        """获取token使用统计"""
        return {
            "total_tokens": self.total_tokens,
            "model": self.model
        }


def _parse_arguments(raw: str, show_warning: bool = False) -> dict:
    """
    把工具参数的 JSON 字符串解析为 dict。

    解析失败（模型偶尔输出残缺 JSON）时返回 {}，由工具自报参数错误，
    模型拿到错误信息后可自行修正重试。
    """
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        if show_warning:
            print(f"⚠️  工具参数 JSON 解析失败：{raw}")
        return {}
    if isinstance(parsed, dict):
        return parsed
    # 模型直接输出裸值（如 "2+3"）时包一层，避免丢信息
    return {"value": parsed}


if __name__ == "__main__":
    client = LLMClient()

    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你好，请用一句话介绍自己。"},
    ]

    reply = client.chat(messages)
    print(f"模型回复: {reply.content}")
    print(f"Token 消耗: {client.get_token_usage()}")
