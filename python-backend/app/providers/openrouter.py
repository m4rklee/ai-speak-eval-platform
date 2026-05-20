import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.openrouter_config import (
    _OPENROUTER_DEFAULT_HEADERS,
    create_openrouter_http_client,
    get_openrouter_client,
    openrouter_http_proxy,
)
from app.providers.base import ChatResult, ModelProvider, NormalizedModel
from app.utils.audio_response import parse_chat_message, parse_stream_audio_delta
from app.utils.cost_calculator import CostCalculator


settings = get_settings()


class OpenRouterProvider(ModelProvider):
    platform = "openrouter"

    def _client(self):
        return get_openrouter_client()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            **_OPENROUTER_DEFAULT_HEADERS,
        }

    async def fetch_models(self) -> list[NormalizedModel]:
        proxy = openrouter_http_proxy()
        client_kwargs: dict = {"timeout": 60.0}
        if proxy:
            client_kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(
                f"{settings.OPENROUTER_BASE_URL}/models",
                headers=self._headers(),
            )
            response.raise_for_status()
        models: list[NormalizedModel] = []
        for item in response.json().get("data", []):
            vendor_id = item.get("id")
            if not vendor_id:
                continue
            arch = item.get("architecture") or {}
            pricing = item.get("pricing") or {}
            created = item.get("created")
            released = datetime.fromtimestamp(created) if created else None
            models.append(
                NormalizedModel(
                    platform=self.platform,
                    vendor_id=vendor_id,
                    name=item.get("name", vendor_id),
                    description=item.get("description"),
                    provider=vendor_id.split("/", 1)[0] if "/" in vendor_id else vendor_id,
                    context_length=item.get("context_length"),
                    modality=arch.get("modality"),
                    input_modalities=list(arch.get("input_modalities") or []),
                    output_modalities=list(arch.get("output_modalities") or []),
                    input_price=self._price_per_million(pricing.get("prompt")),
                    output_price=self._price_per_million(pricing.get("completion")),
                    released_at=released,
                    model_type="llm",
                    is_china=self._is_china(vendor_id),
                    recommended=1 if self._is_china(vendor_id) else 0,
                    raw_data=json.dumps(item, ensure_ascii=False),
                )
            )
        return models

    @staticmethod
    def _is_gpt_audio_model(vendor_model_id: str) -> bool:
        return "gpt-audio" in vendor_model_id.lower()

    @staticmethod
    def _messages_have_audio_input(messages: list[dict[str, Any]]) -> bool:
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "input_audio":
                    return True
        return False

    async def chat_completion(
        self,
        vendor_model_id: str,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        require_audio_output: bool = False,
        timeout: float = 120.0,
    ) -> ChatResult:
        # OpenRouter gpt-audio：音频输出必须 stream + pcm16（见官方文档与用户脚本）
        if require_audio_output and self._is_gpt_audio_model(vendor_model_id):
            return await self._chat_completion_stream_audio(
                vendor_model_id,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        if (
            self._is_gpt_audio_model(vendor_model_id)
            and self._messages_have_audio_input(messages)
        ):
            return await self._chat_completion_stream_text(
                vendor_model_id,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )

        params: dict[str, Any] = {
            "model": vendor_model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        client = self._client()
        response = await client.chat.completions.create(**params)
        msg = response.choices[0].message
        text, audio_data, audio_format = parse_chat_message(msg)
        usage = getattr(response, "usage", None)
        input_tokens = usage.prompt_tokens if usage else CostCalculator.estimate_tokens(
            json.dumps(messages, ensure_ascii=False)
        )
        output_tokens = usage.completion_tokens if usage else CostCalculator.estimate_tokens(text)
        return ChatResult(
            text=text,
            audio_data=audio_data,
            audio_format=audio_format,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            raw_message=msg,
        )

    async def _chat_completion_stream_audio(
        self,
        vendor_model_id: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> ChatResult:
        params: dict[str, Any] = {
            "model": vendor_model_id,
            "messages": messages,
            "stream": True,
            "modalities": ["text", "audio"],
            "audio": {"voice": "alloy", "format": "pcm16"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        client = self._client()
        stream = await client.chat.completions.create(**params, timeout=timeout)
        text_parts: list[str] = []
        transcript_parts: list[str] = []
        audio_b64_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0

        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                input_tokens = usage.prompt_tokens or input_tokens
                output_tokens = usage.completion_tokens or output_tokens
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text_parts.append(delta.content)
            audio = getattr(delta, "audio", None)
            if audio:
                data, transcript = parse_stream_audio_delta(audio)
                if data:
                    audio_b64_parts.append(data)
                if transcript:
                    transcript_parts.append(transcript)

        text = "".join(text_parts) or "".join(transcript_parts)
        audio_data = "".join(audio_b64_parts) if audio_b64_parts else None
        if not audio_data:
            hint = "（仅有文本/转写）" if text else ""
            raise RuntimeError(f"gpt-audio 流式响应未包含音频数据{hint}")

        if not input_tokens:
            input_tokens = CostCalculator.estimate_tokens(json.dumps(messages, ensure_ascii=False))
        if not output_tokens:
            output_tokens = CostCalculator.estimate_tokens(text or audio_data or "")

        return ChatResult(
            text=text,
            audio_data=audio_data,
            audio_format="pcm16" if audio_data else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def _chat_completion_stream_text(
        self,
        vendor_model_id: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> ChatResult:
        """gpt-audio + 音频输入 → 文本输出（与脚本 audio-in 模式一致，使用 stream）"""
        params: dict[str, Any] = {
            "model": vendor_model_id,
            "messages": messages,
            "stream": True,
            "modalities": ["text"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        client = self._client()
        stream = await client.chat.completions.create(**params, timeout=timeout)
        parts: list[str] = []
        input_tokens = 0
        output_tokens = 0
        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                input_tokens = usage.prompt_tokens or input_tokens
                output_tokens = usage.completion_tokens or output_tokens
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                parts.append(delta.content)
        text = "".join(parts)
        if not input_tokens:
            input_tokens = CostCalculator.estimate_tokens(json.dumps(messages, ensure_ascii=False))
        if not output_tokens:
            output_tokens = CostCalculator.estimate_tokens(text)
        return ChatResult(
            text=text,
            audio_data=None,
            audio_format=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _price_per_million(self, price: str | float | None) -> Decimal | None:
        if price is None:
            return None
        return Decimal(str(price)) * Decimal("1000000")

    def _is_china(self, vendor_id: str) -> int:
        china = ["qwen", "alibaba", "baidu", "tencent", "zhipu", "deepseek", "moonshot", "bytedance"]
        lower = vendor_id.lower()
        return 1 if any(p in lower for p in china) else 0
