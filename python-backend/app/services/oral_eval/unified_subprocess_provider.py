"""PronunciationProvider backed by unified MultiPA + APG-MOS daemon."""
from typing import Any

from app.services.oral_eval.pronunciation_provider import PronunciationProvider
from app.services.oral_eval.unified_eval_runner import score_single_wav


class UnifiedSubprocessPronunciationProvider(PronunciationProvider):
    async def score(self, audio_wav_bytes: bytes, reference_text: str) -> dict[str, Any]:
        return await score_single_wav(
            audio_wav_bytes,
            model_name="inline_eval",
            reference_text=reference_text,
        )
