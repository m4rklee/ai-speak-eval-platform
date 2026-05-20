"""单条音频 → 教师模式回复（文本 + 可选音频）。"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Optional

from app.core.errors import BusinessException, ErrorCode
from app.providers.registry import get_provider
from app.schemas.conversation import AudioInput
from app.utils.audio_pcm import pcm16_base64_to_wav_bytes
from app.utils.model_id import normalize_model_id, split_model_id, vendor_model_id
from app.utils.oral_practice import build_oral_practice_messages, default_system_prompt

logger = logging.getLogger(__name__)


def validate_api_configured() -> None:
    from app.services.oral_gen.questionwav import health_check

    h = health_check()
    if not h.get("api_configured"):
        raise BusinessException(
            ErrorCode.OPERATION_ERROR,
            "未配置 OpenRouter 或 AiHubMix API Key",
        )


def guess_audio_format(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"wav", "mp3", "flac", "ogg", "m4a", "mp4"}:
        return suffix if suffix != "mp4" else "m4a"
    return "wav"


def audio_bytes_to_b64(path: str) -> tuple[str, str]:
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        raise ValueError("音频文件为空")
    return base64.b64encode(data).decode("utf-8"), guess_audio_format(path)


def save_audio_to_wav_file(audio_b64: Optional[str], audio_format: Optional[str], out_path: str) -> bool:
    if not audio_b64:
        return False
    fmt = (audio_format or "wav").lower()
    try:
        if fmt in ("pcm16", "pcm"):
            wav_bytes = pcm16_base64_to_wav_bytes(audio_b64)
        else:
            wav_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        logger.warning("decode audio failed: %s", e)
        return False
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(wav_bytes)
    return True


def save_text_file(text: str, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text or "")


async def generate_reply(
    model_id: str,
    wav_path: str,
    *,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """对单条 wav 调用模型，返回 stem/text/audio/error 等。"""
    stem = Path(wav_path).stem
    normalized = normalize_model_id(model_id)
    platform, _ = split_model_id(normalized)
    vendor = vendor_model_id(normalized)

    try:
        b64, fmt = audio_bytes_to_b64(wav_path)
    except (OSError, ValueError) as e:
        return {
            "stem": stem,
            "text": "",
            "audioSaved": False,
            "inputTokens": 0,
            "outputTokens": 0,
            "error": str(e)[:300],
        }

    messages = build_oral_practice_messages(
        audio_inputs=[AudioInput(data=b64, format=fmt)],
        system_prompt=default_system_prompt(),
        user_message_mode="audio_only",
    )

    try:
        provider = get_provider(platform)
        result = await provider.chat_completion(
            vendor,
            messages,
            stream=False,
            temperature=0.7,
            max_tokens=4000,
            require_audio_output=True,
            timeout=timeout,
        )
        text = (result.text or "").strip()
        if not text and not result.audio_data:
            return {
                "stem": stem,
                "text": "",
                "audioSaved": False,
                "audioFormat": result.audio_format,
                "inputTokens": result.input_tokens or 0,
                "outputTokens": result.output_tokens or 0,
                "error": "模型未返回文本或音频，请确认所选模型支持音频输出",
            }
        return {
            "stem": stem,
            "text": text,
            "audioBase64": result.audio_data,
            "audioFormat": result.audio_format or "wav",
            "audioSaved": bool(result.audio_data),
            "inputTokens": result.input_tokens or 0,
            "outputTokens": result.output_tokens or 0,
            "error": None,
        }
    except Exception as e:
        logger.warning("oral_gen infer failed stem=%s: %s", stem, e)
        return {
            "stem": stem,
            "text": "",
            "audioSaved": False,
            "inputTokens": 0,
            "outputTokens": 0,
            "error": str(e)[:300],
        }


def persist_result(
    job_dir: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    """写入 text/ 与 audio/ 子目录，返回 VO 行。"""
    stem = row.get("stem", "")
    text = row.get("text") or ""
    err = row.get("error")
    text_path = os.path.join(job_dir, "text", f"{stem}.txt")
    audio_path = os.path.join(job_dir, "audio", f"{stem}.wav")

    if err:
        save_text_file(f"[ERROR] {err}", text_path)
        audio_ok = False
    else:
        save_text_file(text, text_path)
        audio_ok = save_audio_to_wav_file(
            row.get("audioBase64"),
            row.get("audioFormat"),
            audio_path,
        )

    return {
        "stem": stem,
        "text": text if not err else "",
        "hasAudio": audio_ok,
        "error": err,
        "inputTokens": row.get("inputTokens", 0),
        "outputTokens": row.get("outputTokens", 0),
    }


def persist_result_flat(
    work_dir: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    """写入 work_dir 根目录 {stem}.txt / {stem}.wav（综合评测一站式用）。"""
    stem = row.get("stem", "")
    text = row.get("text") or ""
    err = row.get("error")
    text_path = os.path.join(work_dir, f"{stem}.txt")
    audio_path = os.path.join(work_dir, f"{stem}.wav")

    if err:
        save_text_file(f"[ERROR] {err}", text_path)
        audio_ok = False
    else:
        save_text_file(text, text_path)
        audio_ok = save_audio_to_wav_file(
            row.get("audioBase64"),
            row.get("audioFormat"),
            audio_path,
        )

    return {
        "stem": stem,
        "text": text if not err else "",
        "hasAudio": audio_ok,
        "error": err,
        "inputTokens": row.get("inputTokens", 0),
        "outputTokens": row.get("outputTokens", 0),
    }
