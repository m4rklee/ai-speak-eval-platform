"""
对话服务类
"""
import json
import re
from typing import AsyncIterator

from app.core.openrouter_config import get_openrouter_client


class ChatService:
    @staticmethod
    async def generate_variants(
        prompt: str,
        count: int = 3,
        model_name: str = "deepseek/deepseek-chat"
    ) -> list[str]:
        """
        调用大模型自动生成提示词变体
        """
        system_prompt = """你是一个专业的 Prompt 工程师。请根据用户给出的基础提示词，生成指定数量的不同表达风格的变体。

要求：
1. 每个变体保持原意不变，但表达方式不同
2. 覆盖不同的提示词技巧，例如：直接提问、角色扮演、思维链(CoT)、Few-shot示例、结构化输出等
3. 严格按以下 JSON 格式返回，不要包含 markdown 代码块或其他说明：
{"variants": ["变体1内容", "变体2内容", "变体3内容"]}"""

        user_prompt = f'请为基础提示词生成 {count} 个变体：\\n\\n基础提示词：{prompt}'

        client = get_openrouter_client()
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=3000,
            extra_headers={
                "HTTP-Referer": "https://codefather.cn",
                "X-Title": "AI Evaluation Platform"
            }
        )

        content = response.choices[0].message.content or ""

        # 策略1：尝试 JSON 解析
        try:
            # 提取 JSON 对象（兼容换行）
            json_match = re.search(r'\{[\s\S]*"variants"[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data.get("variants"), list):
                    variants = [str(v).strip() for v in data["variants"] if str(v).strip()]
                    if variants:
                        return variants[:count]
        except (json.JSONDecodeError, ValueError):
            pass

        # 策略2：正则提取编号列表（1. xxx 或 1、xxx）
        variants = []
        for line in content.strip().split("\n"):
            line = line.strip()
            match = re.match(r'^[\d一二三四五六]+[.．、)\s]+(.+)$', line)
            if match:
                text = match.group(1).strip()
                if text and text not in variants:
                    variants.append(text)

        # 策略3：按空行分段提取
        if not variants:
            paragraphs = [p.strip() for p in re.split(r'\n{2,}', content) if p.strip()]
            for p in paragraphs:
                # 去掉可能的 markdown 列表标记
                cleaned = re.sub(r'^[-*•]\s*', '', p).strip()
                if cleaned and cleaned not in variants:
                    variants.append(cleaned)

        return variants[:count]

    @staticmethod
    async def stream_chat(
        message: str,
        model_name: str = "deepseek/deepseek-chat"
    ) -> AsyncIterator[str]:
        """
        流式对话
        """
        client = get_openrouter_client()
        stream = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": message}],
            temperature=0.7,
            max_tokens=2000,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

    @staticmethod
    async def simple_chat(
        message: str,
        model_name: str = 'deepseek/deepseek-chat'
    ) -> str:
        """
        简单对话（非流式）
        """
        client = get_openrouter_client()
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": message}],
            temperature=0.7,
            max_tokens=2000
        )
        content = response.choices[0].message.content
        return content or ""
