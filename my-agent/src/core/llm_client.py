"""
LLM 客户端封装
统一管理大模型调用，支持多种 API 提供商
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

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

    def chat(self, messages: list, temperature: float = 0.7) -> str:
        """
        发送对话请求
        
        Args:
            messages: 对话历史，格式为 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数，越高越随机（0~2）
            
        Returns:
            模型回复的文本内容
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )

        if response.usage is not None:
            self.total_tokens += response.usage.total_tokens

        return response.choices[0].message.content

    def chat_stream(self, messages: list, temperature: float = 0.7) -> str:
        """流式对话，边接收边打印，返回完整回复文本"""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
            # 流式默认不带 usage；打开后会在最后一个 chunk 里附带整次请求的 token 统计
            stream_options={"include_usage": True},
        )

        full_response = ""
        for chunk in stream:
            # 末尾 usage chunk 的 choices 常为空，必须先判空再读 delta
            if chunk.choices:
                delta = chunk.choices[0].delta.content or ""
                print(delta, end="", flush=True)
                # 拼全文
                full_response += delta
            # 累加usgae
            if chunk.usage is not None:
                self.total_tokens += chunk.usage.total_tokens
        print()
        return full_response

    def get_token_usage(self) -> dict:
        """获取token使用统计"""
        return {
            "total_tokens": self.total_tokens,
            "model": self.model
        }

if __name__ == "__main__":
    client = LLMClient()

    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你好，请用一句话介绍自己。"},
    ]

    reply = client.chat(messages)
    print(f"模型回复: {reply}")
    print(f"Token 消耗: {client.get_token_usage()}")
