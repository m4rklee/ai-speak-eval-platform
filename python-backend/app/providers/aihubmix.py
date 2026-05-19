import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.providers.base import ChatResult, ModelProvider, NormalizedModel
from app.utils.audio_response import parse_chat_message
from app.utils.cost_calculator import CostCalculator


settings = get_settings()


class AiHubMixProvider(ModelProvider):
    platform = "aihubmix"

    def _chat_base_url(self) -> str:
        """OpenAI 兼容对话： https://aihubmix.com/v1/chat/completions"""
        base = settings.AIHUBMIX_BASE_URL.rstrip("/")
        if base.endswith("/api/v1"):
            return base[: -len("/api/v1")] + "/v1"
        return base

    def _models_base_url(self) -> str:
        """模型元数据： https://aihubmix.com/api/v1/models"""
        explicit = getattr(settings, "AIHUBMIX_MODELS_URL", "") or ""
        if explicit.strip():
            return explicit.rstrip("/")
        base = settings.AIHUBMIX_BASE_URL.rstrip("/")
        if base.endswith("/v1") and not base.endswith("/api/v1"):
            return base[: -len("/v1")] + "/api/v1"
        if base.endswith("/api/v1"):
            return base
        return "https://aihubmix.com/api/v1"

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=settings.AIHUBMIX_API_KEY,
            base_url=self._chat_base_url(),
        )

    async def fetch_models(self) -> list[NormalizedModel]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._models_base_url()}/models",
                headers={"Authorization": f"Bearer {settings.AIHUBMIX_API_KEY}"},
                timeout=60.0,
            )
            response.raise_for_status()
        payload = response.json()
        items = payload.get("data", []) if isinstance(payload, dict) else []
        models_by_id: dict[str, NormalizedModel] = {}
        for item in items:
            raw_id = item.get("model_id") or item.get("id")
            if not raw_id:
                continue
            # AiHubMix 偶有仅大小写不同的重复 ID；MySQL 默认 collation 不区分大小写
            vendor_id = str(raw_id).lower()
            if vendor_id in models_by_id:
                continue
            input_mods = self._split_modalities(item.get("input_modalities"))
            model_type = (item.get("types") or item.get("type") or "llm").lower()
            output_mods = self._infer_output_modalities(model_type, input_mods)
            pricing = item.get("pricing") or {}
            display_name = (item.get("model_name") or "").strip() or vendor_id
            description = item.get("desc")
            models_by_id[vendor_id] = NormalizedModel(
                    platform=self.platform,
                    vendor_id=vendor_id,
                    name=display_name[:200],
                    description=description,
                    provider=vendor_id.split("-")[0] if "-" in vendor_id else vendor_id,
                    context_length=item.get("context_length"),
                    modality=self._modality_string(input_mods, output_mods),
                    input_modalities=input_mods,
                    output_modalities=output_mods,
                    input_price=self._price_per_million_from_1k(pricing.get("input")),
                    output_price=self._price_per_million_from_1k(pricing.get("output")),
                    released_at=None,
                    model_type=model_type,
                    is_china=self._is_china(vendor_id),
                    recommended=0,
                    raw_data=json.dumps(item, ensure_ascii=False),
                )
        return list(models_by_id.values())

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
        params: dict[str, Any] = {
            "model": vendor_model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        if require_audio_output:
            params["modalities"] = ["text", "audio"]
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

    def _split_modalities(self, value: Any) -> list[str]:
        if not value:
            return ["text"]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [p.strip() for p in str(value).split(",") if p.strip()]

    def _infer_output_modalities(self, model_type: str, input_mods: list[str]) -> list[str]:
        if model_type == "tts":
            return ["audio"]
        if model_type == "stt":
            return ["text"]
        if model_type in ("llm", "image_generation", "video"):
            return ["text"]
        if "audio" in input_mods:
            return ["text"]
        return ["text"]

    def _modality_string(self, input_mods: list[str], output_mods: list[str]) -> str:
        return f"{'+'.join(input_mods) or 'text'}->{'+'.join(output_mods) or 'text'}"

    def _price_per_million_from_1k(self, price: Any) -> Decimal | None:
        if price is None:
            return None
        return Decimal(str(price)) * Decimal("1000")

    def _is_china(self, vendor_id: str) -> int:
        china = ["qwen", "deepseek", "zhipu", "moonshot", "baidu", "glm"]
        lower = vendor_id.lower()
        return 1 if any(p in lower for p in china) else 0
