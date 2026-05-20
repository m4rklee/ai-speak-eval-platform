"""综合评测任务进度（Redis oral_combined:job:）。"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from app.db.redis import get_redis
from app.services.unified_eval_progress import read_live_progress

JOB_KEY_PREFIX = "oral_combined:job:"
JOB_TTL_SEC = 86400

SPEECH_PROGRESS_LO = 0
SPEECH_PROGRESS_HI = 50
CONTENT_PROGRESS_LO = 50
CONTENT_PROGRESS_HI = 99

PIPELINE_GEN_PROGRESS_LO = 0
PIPELINE_GEN_PROGRESS_HI = 45
PIPELINE_EVAL_PROGRESS_LO = 45
PIPELINE_EVAL_PROGRESS_HI = 99


def job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def progress_detail_vo(detail: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not detail:
        return None
    return {
        "phase": detail.get("phase"),
        "phaseLabel": detail.get("phase_label", detail.get("phaseLabel", "")),
        "current": detail.get("current", 0),
        "total": detail.get("total", 0),
        "elapsedSec": detail.get("elapsed_sec", detail.get("elapsedSec")),
        "etaSec": detail.get("eta_sec", detail.get("etaSec")),
        "elapsedText": detail.get("elapsed_text", detail.get("elapsedText", "")),
        "etaText": detail.get("eta_text", detail.get("etaText", "")),
        "ratePerSec": detail.get("rate_per_sec", detail.get("ratePerSec")),
        "message": detail.get("message", ""),
        "tqdmLine": detail.get("tqdm_line", detail.get("tqdmLine", "")),
        "warningLine": detail.get("warning_line", detail.get("warningLine")),
    }


def _format_duration(sec: float) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class PipelineGenProgressReporter:
    """一站式：回复生成阶段，进度 0–45%。"""

    def __init__(self, job_id: str, total: int) -> None:
        self.job_id = job_id
        self.total = max(1, total)
        self.started_at = time.time()

    async def update(self, current: int, message: str = "") -> None:
        redis = get_redis()
        raw = await redis.get(job_key(self.job_id))
        if not raw:
            return
        payload = json.loads(raw)
        elapsed = time.time() - self.started_at
        pct = (
            int(min(PIPELINE_GEN_PROGRESS_HI - 1, (current / self.total) * PIPELINE_GEN_PROGRESS_HI))
            if current < self.total
            else PIPELINE_GEN_PROGRESS_HI
        )
        elapsed_text = _format_duration(elapsed)
        tqdm_line = f"回复生成 [{current}/{self.total}] {pct}% | {elapsed_text}"
        if message:
            tqdm_line += f" | {message}"
        payload["progress"] = pct
        payload["status"] = "generating"
        payload["progress_detail"] = {
            "phase": "generating",
            "phase_label": "回复生成",
            "current": current,
            "total": self.total,
            "elapsed_sec": round(elapsed, 1),
            "elapsed_text": elapsed_text,
            "message": message,
            "tqdm_line": tqdm_line,
        }
        await redis.set(
            job_key(self.job_id),
            json.dumps(payload, ensure_ascii=False),
            ex=JOB_TTL_SEC,
        )


class OralCombinedProgressReporter:
    """并行语音+内容：语音占 progress_lo–mid%，内容占 mid–progress_hi。"""

    def __init__(
        self,
        job_id: str,
        total_pairs: int,
        *,
        progress_lo: int = SPEECH_PROGRESS_LO,
        progress_hi: int = CONTENT_PROGRESS_HI,
    ) -> None:
        self.job_id = job_id
        self.total_pairs = max(1, total_pairs)
        self.progress_lo = progress_lo
        self.progress_hi = progress_hi
        self.speech_lo = progress_lo
        self.speech_hi = progress_lo + (progress_hi - progress_lo) // 2
        self.content_lo = self.speech_hi
        self.content_hi = progress_hi
        self.started_at = time.time()
        self._speech_done = False
        self._content_done = False
        self._content_current = 0
        self._content_message = ""
        self._live_poll_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def _load_payload(self) -> Optional[dict[str, Any]]:
        redis = get_redis()
        raw = await redis.get(job_key(self.job_id))
        if not raw:
            return None
        return json.loads(raw)

    async def _save_payload(self, payload: dict[str, Any]) -> None:
        redis = get_redis()
        await redis.set(
            job_key(self.job_id),
            json.dumps(payload, ensure_ascii=False),
            ex=JOB_TTL_SEC,
        )

    def _speech_fraction(self, live: Optional[dict[str, Any]]) -> float:
        if self._speech_done:
            return 1.0
        if not live:
            return 0.0
        seg = max(1, int(live.get("multipaTotal") or self.total_pairs))
        mp = min(seg, int(live.get("multipaCurrent") or 0))
        apg_total = int(live.get("apgTotal") or seg * 2)
        apg_files = max(1, apg_total // 2) if apg_total else seg
        ap = min(seg, int(live.get("apgCurrent") or 0) // 2)
        if live.get("multipaDone") and not live.get("apgDone"):
            return ap / seg
        if live.get("apgDone") and not live.get("multipaDone"):
            return mp / seg
        return min(1.0, max(mp, ap) / seg)

    def _content_fraction(self) -> float:
        if self._content_done:
            return 1.0
        return min(1.0, self._content_current / self.total_pairs)

    def _calc_progress(self, live: Optional[dict[str, Any]]) -> int:
        speech_span = max(1, self.speech_hi - self.speech_lo)
        content_span = max(1, self.content_hi - self.content_lo)
        speech_part = self._speech_fraction(live) * speech_span
        content_part = self._content_fraction() * content_span
        total = self.speech_lo + speech_part + (self.content_lo - self.speech_hi) + content_part
        if self._speech_done and self._content_done:
            return 100
        return min(self.progress_hi, max(self.progress_lo, int(total)))

    def _build_detail(self, live: Optional[dict[str, Any]]) -> dict[str, Any]:
        elapsed = time.time() - self.started_at
        progress = self._calc_progress(live)
        speech_pct = int(self._speech_fraction(live) * 100)
        content_pct = int(self._content_fraction() * 100)

        parts: list[str] = []
        if not self._speech_done:
            if live:
                mp = live.get("multipaCurrent", 0)
                mp_t = live.get("multipaTotal") or self.total_pairs
                ap = live.get("apgCurrent", 0)
                ap_t = live.get("apgTotal") or self.total_pairs * 2
                parts.append(f"语音 MultiPA {mp}/{mp_t} APG {ap}/{ap_t}")
            else:
                parts.append("语音评测启动中")
        else:
            parts.append("语音 ✓")

        if not self._content_done:
            parts.append(f"内容 {self._content_current}/{self.total_pairs}")
            if self._content_message:
                parts.append(self._content_message)
        else:
            parts.append("内容 ✓")

        phase_label = "综合评测"
        if not self._speech_done and not self._content_done:
            phase = "parallel"
            phase_label = "语音 + 内容并行"
        elif not self._speech_done:
            phase = "speech"
            phase_label = "语音评测"
        elif not self._content_done:
            phase = "content"
            phase_label = "内容评测"
        else:
            phase = "done"
            phase_label = "完成"

        elapsed_text = _format_duration(elapsed)
        tqdm_line = f"综合 [{progress}%] 语音 {speech_pct}% | 内容 {content_pct}% | {elapsed_text}"
        if parts:
            tqdm_line += " | " + " · ".join(parts)

        return {
            "phase": phase,
            "phase_label": phase_label,
            "current": self._content_current + int(self._speech_fraction(live) * self.total_pairs),
            "total": self.total_pairs * 2,
            "elapsed_sec": round(elapsed, 1),
            "eta_sec": None,
            "elapsed_text": elapsed_text,
            "eta_text": "",
            "rate_per_sec": None,
            "message": " · ".join(parts),
            "tqdm_line": tqdm_line,
        }

    async def _persist(self, *, status: Optional[str] = None) -> None:
        async with self._lock:
            payload = await self._load_payload()
            if not payload:
                return
            live = await read_live_progress(self.job_id)
            detail = self._build_detail(live)
            payload["progress"] = self._calc_progress(live)
            payload["progress_detail"] = detail
            if status:
                payload["status"] = status
            await self._save_payload(payload)

    async def _live_poll_loop(self) -> None:
        try:
            while not (self._speech_done and self._content_done):
                await self._persist(status="running")
                await asyncio.sleep(0.8)
        except asyncio.CancelledError:
            pass

    async def start(self) -> None:
        payload = await self._load_payload()
        if payload:
            payload["status"] = "running"
            payload["progress"] = 0
            await self._save_payload(payload)
        self._live_poll_task = asyncio.create_task(self._live_poll_loop())

    async def update_content(self, current: int, message: str = "") -> None:
        self._content_current = current
        self._content_message = message
        await self._persist(status="running")

    async def mark_speech_done(self) -> None:
        self._speech_done = True
        await self._persist(status="running")

    async def mark_content_done(self) -> None:
        self._content_done = True
        await self._persist(status="running")

    async def finish(self, *, success: bool) -> None:
        self._speech_done = True
        self._content_done = True
        if self._live_poll_task:
            self._live_poll_task.cancel()
            try:
                await self._live_poll_task
            except asyncio.CancelledError:
                pass
            self._live_poll_task = None
        payload = await self._load_payload()
        if not payload:
            return
        detail = self._build_detail(None)
        detail["phase"] = "done"
        detail["phase_label"] = "完成" if success else "失败"
        payload["progress"] = 100
        payload["progress_detail"] = detail
        payload["status"] = "completed" if success else "failed"
        await self._save_payload(payload)
