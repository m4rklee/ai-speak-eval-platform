"""从 Chat Completions 响应中解析文本与音频"""
from typing import Any, Optional, Tuple


def parse_stream_audio_delta(audio: Any) -> Tuple[Optional[str], Optional[str]]:
    """流式 chunk 的 delta.audio（OpenRouter 常为 dict）"""
    if not audio:
        return None, None
    if isinstance(audio, dict):
        return audio.get("data"), audio.get("transcript")
    return getattr(audio, "data", None), getattr(audio, "transcript", None)


def parse_chat_message(message: Any) -> Tuple[str, Optional[str], Optional[str]]:
    text_parts: list[str] = []
    audio_data: Optional[str] = None
    audio_format: Optional[str] = None

    if message is None:
        return "", None, None

    content = getattr(message, "content", None)
    if isinstance(content, str) and content:
        text_parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                ptype = part.get("type")
                if ptype == "text":
                    text_parts.append(part.get("text", ""))
                elif ptype in ("audio", "output_audio"):
                    audio_data = part.get("data") or part.get("audio", {}).get("data")
                    audio_format = part.get("format") or part.get("audio", {}).get("format")
            else:
                ptype = getattr(part, "type", None)
                if ptype == "text":
                    text_parts.append(getattr(part, "text", "") or "")
    elif content:
        text_parts.append(str(content))

    audio_obj = getattr(message, "audio", None)
    if audio_obj:
        if isinstance(audio_obj, dict):
            audio_data = audio_obj.get("data") or audio_data
            audio_format = audio_obj.get("format") or audio_format
        else:
            audio_data = getattr(audio_obj, "data", None) or audio_data
            audio_format = getattr(audio_obj, "format", None) or audio_format

    return "".join(text_parts), audio_data, audio_format
