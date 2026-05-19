"""HTTP 发音评测服务适配"""
import base64
from typing import Any

import httpx

from app.services.oral_eval.pronunciation_provider import PronunciationProvider


class HttpPronunciationProvider(PronunciationProvider):
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def score(self, audio_wav_bytes: bytes, reference_text: str) -> dict[str, Any]:
        url = f"{self.base_url}/score"
        payload = {
            "audio_base64": base64.b64encode(audio_wav_bytes).decode("ascii"),
            "audio_format": "wav",
            "reference_text": reference_text,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return {
            "accuracy": float(data.get("accuracy", data.get("pronunciation", 0))),
            "fluency": float(data.get("fluency", 0)),
            "naturalness": float(data.get("naturalness", data.get("prosody", 0))),
            "raw": data,
            "status": "ok",
        }
