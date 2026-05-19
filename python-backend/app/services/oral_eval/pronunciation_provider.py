"""发音评测抽象"""
from abc import ABC, abstractmethod
from typing import Any


class PronunciationProvider(ABC):
    @abstractmethod
    async def score(self, audio_wav_bytes: bytes, reference_text: str) -> dict[str, Any]:
        """返回 accuracy, fluency, naturalness (0-100) 及 raw"""
