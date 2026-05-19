"""PCM16 与 WAV 转换（OpenRouter gpt-audio 流式输出）"""
import base64
import struct


def pcm16_base64_to_wav_bytes(base64_pcm: str, sample_rate: int = 24000) -> bytes:
    pcm = base64.b64decode(base64_pcm)
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + pcm


def output_audio_json_to_wav_bytes(output_audio_json: str) -> tuple[bytes, str]:
    """解析 outputAudio JSON，返回 (wav_bytes, source_format)"""
    import json

    obj = json.loads(output_audio_json)
    fmt = (obj.get("format") or "wav").lower()
    data = obj.get("data") or ""
    if fmt in ("pcm16", "pcm"):
        return pcm16_base64_to_wav_bytes(data), fmt
    return base64.b64decode(data), fmt
