"""单题听力推理：本地音频 + 模型库 Provider。"""
from __future__ import annotations

import base64
import logging
from typing import Any

from app.core.errors import BusinessException, ErrorCode
from app.providers.registry import get_provider
from app.utils.audio_input import prepare_input_audio_bytes
from app.utils.listen_eval_benchmark import resolve_audio_path
from app.utils.model_id import normalize_model_id, split_model_id, vendor_model_id

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Choose the most suitable answer from options A, B, C, D and E. "
    "You must respond with only A, B, C, D or E."
)


def build_instruction(item: dict[str, Any], prompt_prefix: str = DEFAULT_PROMPT) -> str:
    lines = [
        prompt_prefix,
        "",
        f"Question: {item['question']}",
        "",
        f"A. {item.get('choice_a', '')}",
        f"B. {item.get('choice_b', '')}",
        f"C. {item.get('choice_c', '')}",
        f"D. {item.get('choice_d', '')}",
        f"E. {item.get('choice_e', '')}",
    ]
    return "\n".join(lines)


async def infer_item(
    model_id: str,
    item: dict[str, Any],
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """返回带 response / error 字段的结果行（保留原题字段）。"""
    normalized = normalize_model_id(model_id)
    platform, _ = split_model_id(normalized)
    vendor = vendor_model_id(normalized)

    try:
        audio_path = resolve_audio_path(item)
    except FileNotFoundError as e:
        return {**item, "response": "", "error": str(e)[:300]}

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    except OSError as e:
        return {**item, "response": "", "error": f"读取音频失败: {e}"[:300]}

    try:
        payload_bytes, fmt = prepare_input_audio_bytes(audio_bytes, path_hint=audio_path)
    except ValueError as e:
        return {**item, "response": "", "error": str(e)[:300]}

    b64 = base64.b64encode(payload_bytes).decode("utf-8")
    instruction = build_instruction(item)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"data": b64, "format": fmt},
                },
                {"type": "text", "text": instruction},
            ],
        }
    ]

    try:
        provider = get_provider(platform)
        result = await provider.chat_completion(
            vendor,
            messages,
            stream=False,
            temperature=0.0,
            max_tokens=32,
            require_audio_output=False,
            timeout=timeout,
        )
        text = (result.text or "").strip()
        return {
            **item,
            "response": text,
            "error": None,
            "model": normalized,
            "inputMode": "audio",
            "input_tokens": int(result.input_tokens or 0),
            "output_tokens": int(result.output_tokens or 0),
        }
    except Exception as e:
        logger.warning("listen infer failed id=%s: %s", item.get("id"), e)
        return {
            **item,
            "response": "",
            "error": str(e)[:300],
            "model": normalized,
            "inputMode": "audio",
            "input_tokens": 0,
            "output_tokens": 0,
        }


def validate_model_configured() -> None:
    from app.utils.listen_eval_benchmark import health_check

    h = health_check()
    if not h.get("apiConfigured"):
        raise BusinessException(
            ErrorCode.OPERATION_ERROR,
            "未配置 OpenRouter 或 AiHubMix API Key，无法调用模型",
        )
