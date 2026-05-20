"""评测音频输入：检测真实格式并规范化为 OpenRouter input_audio 可接受的数据。"""
from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def is_riff_wav(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def detect_audio_format(data: bytes) -> str:
    if not data:
        return "unknown"
    if is_riff_wav(data):
        return "wav"
    if data[:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:4] == b"OggS":
        return "ogg"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "m4a"
    return "unknown"


def _transcode_to_wav_bytes(data: bytes) -> bytes:
    import numpy as np
    import soundfile as sf

    with io.BytesIO(data) as src:
        audio, sample_rate = sf.read(src, dtype="float32", always_2d=True)
    if audio.shape[1] > 1:
        audio = np.mean(audio, axis=1, keepdims=True)
    out = io.BytesIO()
    sf.write(out, audio, sample_rate, format="WAV", subtype="PCM_16")
    return out.getvalue()


def prepare_input_audio_bytes(data: bytes, *, path_hint: str = "") -> tuple[bytes, str]:
    """返回 (payload_bytes, input_audio.format)。"""
    if not data:
        raise ValueError("音频文件为空")

    detected = detect_audio_format(data)
    if detected == "wav":
        return data, "wav"
    if detected == "mp3":
        return data, "mp3"

    suffix = Path(path_hint).suffix.lower().lstrip(".") if path_hint else ""
    if detected == "unknown" and suffix == "mp3":
        return data, "mp3"

    try:
        wav_bytes = _transcode_to_wav_bytes(data)
        if is_riff_wav(wav_bytes):
            return wav_bytes, "wav"
    except Exception as exc:
        logger.warning("audio transcode failed path=%s detected=%s: %s", path_hint, detected, exc)

    if detected in {"flac", "ogg", "m4a"}:
        raise ValueError(f"无法将 {detected} 音频转为 wav，请检查文件是否损坏")

    raise ValueError("音频格式无效或不受支持（需 wav/mp3/flac 等）")
