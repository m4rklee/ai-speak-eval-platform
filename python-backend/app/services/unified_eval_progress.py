"""Uni 评测任务进度上报（Redis + daemon 实时进度）。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

from app.db.redis import get_redis

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "uni_eval:job:"
JOB_TTL_SEC = 86400

PHASE_LABELS: dict[str, str] = {
    "preparing": "准备中",
    "multipa": "MultiPA 发音评测",
    "apg": "APG-MOS 评分",
    "parallel": "MultiPA + APG-MOS 并行评测",
    "merging": "合并结果",
    "done": "完成",
}

PHASE_PROGRESS: dict[str, tuple[int, int]] = {
    "preparing": (0, 5),
    "multipa": (5, 93),
    "apg": (5, 93),
    "parallel": (5, 93),
    "merging": (93, 99),
    "done": (100, 100),
}


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def live_key(job_id: str) -> str:
    """Deprecated: live progress uses JSON files under /tmp/uni_eval_live."""
    return job_id


def _format_duration(sec: float) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


async def init_live_progress(job_id: str, *, multipa_total: int, apg_total: int) -> None:
    await asyncio.to_thread(
        _sync_init_live,
        job_id,
        multipa_total=multipa_total,
        apg_total=apg_total,
    )


async def clear_live_progress(job_id: str) -> None:
    await asyncio.to_thread(_sync_clear_live, job_id)


async def read_live_progress(job_id: str) -> Optional[dict[str, Any]]:
    return await asyncio.to_thread(_sync_read_live, job_id)


def _sync_init_live(job_id: str, *, multipa_total: int, apg_total: int) -> None:
    import sys

    unified_dir = os.environ.get("UNIFIED_EVAL_DIR", "/root/unified-speech-eval")
    if unified_dir not in sys.path:
        sys.path.insert(0, unified_dir)
    from eval_live_progress import init_progress

    init_progress(job_id, multipa_total=multipa_total, apg_total=apg_total)


def _sync_clear_live(job_id: str) -> None:
    import sys

    unified_dir = os.environ.get("UNIFIED_EVAL_DIR", "/root/unified-speech-eval")
    if unified_dir not in sys.path:
        sys.path.insert(0, unified_dir)
    from eval_live_progress import clear_progress

    clear_progress(job_id)


def _sync_read_live(job_id: str) -> Optional[dict[str, Any]]:
    import sys

    unified_dir = os.environ.get("UNIFIED_EVAL_DIR", "/root/unified-speech-eval")
    if unified_dir not in sys.path:
        sys.path.insert(0, unified_dir)
    from eval_live_progress import read_progress

    return read_progress(job_id)


class JobProgressReporter:
    """基于 daemon 上报的真实 current/total 计算进度。"""

    def __init__(self, job_id: str, total_files: int, *, engine: str = "daemon") -> None:
        self.job_id = job_id
        self.total_files = max(1, total_files)
        self.engine = "daemon"
        self.started_at = time.time()
        self.phase = "preparing"
        self.message = ""
        self._ticker: Optional[asyncio.Task] = None

        self._segment_files = self.total_files
        self._files_base_offset = 0

        self._live_multipa_current = 0
        self._live_multipa_total = 0
        self._live_apg_current = 0
        self._live_apg_total = 0
        self._live_multipa_done = False
        self._live_apg_done = False

    async def begin_segment(self, segment_files: int, base_offset: int = 0) -> None:
        """多模型任务：开始评测其中一个模型的 wav 目录。"""
        self._segment_files = max(1, segment_files)
        self._files_base_offset = max(0, base_offset)
        self._live_multipa_current = 0
        self._live_multipa_total = 0
        self._live_apg_current = 0
        self._live_apg_total = 0
        self._live_multipa_done = False
        self._live_apg_done = False
        await init_live_progress(
            self.job_id,
            multipa_total=segment_files,
            apg_total=segment_files * 2,
        )

    def apply_live(self, live: dict[str, Any]) -> None:
        self._live_multipa_current = int(live.get("multipaCurrent") or 0)
        self._live_multipa_total = int(live.get("multipaTotal") or 0)
        self._live_apg_current = int(live.get("apgCurrent") or 0)
        self._live_apg_total = int(live.get("apgTotal") or 0)
        self._live_multipa_done = bool(live.get("multipaDone"))
        self._live_apg_done = bool(live.get("apgDone"))

    def _segment_file_equiv(self) -> int:
        """当前目录内等效已完成文件数（并行时取较慢侧）。"""
        seg = self._segment_files
        mp = min(self._live_multipa_current, seg)
        apg_files = self._live_apg_total // 2 if self._live_apg_total else seg
        apg_files = max(1, apg_files) if self._live_apg_total else seg
        ap = min(self._live_apg_current // 2, seg)

        if self.phase == "parallel":
            if self._live_multipa_done and not self._live_apg_done:
                return ap
            if self._live_apg_done and not self._live_multipa_done:
                return mp
            return min(seg, max(mp, ap))
        if self.phase == "multipa":
            return mp
        if self.phase == "apg":
            return ap
        return min(seg, max(mp, ap))

    def _job_files_done(self) -> int:
        if self.phase == "done":
            return self.total_files
        return min(self.total_files, self._files_base_offset + self._segment_file_equiv())

    def _phase_fraction(self) -> float:
        if self.phase in ("multipa", "apg", "parallel") and self._segment_files > 0:
            return min(1.0, self._segment_file_equiv() / self._segment_files)
        if self.phase == "merging":
            return 1.0
        return 1.0 if self.phase == "done" else 0.0

    def _calc_progress(self) -> int:
        lo, hi = PHASE_PROGRESS.get(self.phase, (0, 100))
        if self.phase in ("multipa", "apg", "parallel"):
            job_frac = self._job_files_done() / self.total_files
            return min(99, int(lo + (hi - lo) * job_frac))
        frac = self._phase_fraction()
        return min(99, int(lo + (hi - lo) * frac))

    def _snapshot(self) -> dict[str, Any]:
        elapsed = time.time() - self.started_at
        job_done = self._job_files_done()
        progress = self._calc_progress()

        rate = job_done / elapsed if elapsed > 0.5 and job_done > 0 else None
        if rate and rate > 0:
            eta = max(0.0, (self.total_files - job_done) / rate)
        else:
            eta = 0.0

        mp_total = self._live_multipa_total or self._segment_files
        ap_total = self._live_apg_total or self._segment_files * 2

        return {
            "phase": self.phase,
            "phaseLabel": PHASE_LABELS.get(self.phase, self.phase),
            "current": job_done,
            "total": self.total_files,
            "multipaCurrent": self._live_multipa_current,
            "multipaTotal": mp_total,
            "apgCurrent": self._live_apg_current,
            "apgTotal": ap_total,
            "multipaDone": self._live_multipa_done,
            "apgDone": self._live_apg_done,
            "elapsedSec": round(elapsed, 1),
            "etaSec": round(eta, 1),
            "elapsedText": _format_duration(elapsed),
            "etaText": _format_duration(eta),
            "ratePerSec": round(rate, 3) if rate else None,
            "message": self.message or PHASE_LABELS.get(self.phase, ""),
            "tqdmLine": self._tqdm_line(elapsed, eta, job_done, mp_total, ap_total),
        }

    def _tqdm_line(
        self,
        elapsed: float,
        eta: float,
        job_done: int,
        mp_total: int,
        ap_total: int,
    ) -> str:
        elapsed_s = _format_duration(elapsed)
        eta_s = _format_duration(eta)
        mp_mark = "✓" if self._live_multipa_done else str(self._live_multipa_current)
        ap_mark = "✓" if self._live_apg_done else str(self._live_apg_current)
        if self.phase == "parallel":
            return (
                f"任务 {job_done}/{self.total_files} | "
                f"MultiPA {mp_mark}/{mp_total} APG {ap_mark}/{ap_total} "
                f"[{elapsed_s}<{eta_s}]"
            )
        label = PHASE_LABELS.get(self.phase, self.phase)
        seg_done = self._segment_file_equiv()
        return f"{label} | {seg_done}/{self._segment_files} | 任务 {job_done}/{self.total_files} [{elapsed_s}<{eta_s}]"

    async def _persist(self, *, status: Optional[str] = None, extra: Optional[dict] = None) -> None:
        redis = get_redis()
        raw = await redis.get(_job_key(self.job_id))
        if not raw:
            return
        payload = json.loads(raw)
        detail = self._snapshot()
        payload["progress"] = self._calc_progress() if status != "completed" else 100
        payload["progress_detail"] = detail
        payload["started_at_ts"] = self.started_at
        if status:
            payload["status"] = status
        if extra:
            payload.update(extra)
        await redis.set(
            _job_key(self.job_id),
            json.dumps(payload, ensure_ascii=False),
            ex=JOB_TTL_SEC,
        )

    async def start(self) -> None:
        self.phase = "preparing"
        self.message = "任务已排队"
        await self._persist(status="running")
        await self._start_ticker()

    async def set_phase(
        self,
        phase: str,
        *,
        current: int = 0,
        total: Optional[int] = None,
        message: str = "",
    ) -> None:
        self.phase = phase
        if total is not None:
            self._segment_files = max(1, total)
        if phase == "multipa":
            self._live_multipa_current = current
        elif phase == "apg":
            self._live_apg_current = current * 2 if current else 0
        self.message = message or PHASE_LABELS.get(phase, "")
        await self._persist()

    async def set_parallel_eval(self, total: Optional[int] = None) -> None:
        self.phase = "parallel"
        self._live_multipa_done = False
        self._live_apg_done = False
        if total is not None:
            self._segment_files = max(1, total)
        self.message = "MultiPA 与 APG-MOS 并行评测中…"
        await self._persist()

    async def mark_multipa_done(self) -> None:
        self._live_multipa_done = True
        self._live_multipa_current = self._live_multipa_total or self._segment_files
        self.message = "MultiPA 已完成，等待 APG-MOS…" if not self._live_apg_done else "并行评测完成"
        await self._persist()

    async def mark_apg_done(self) -> None:
        self._live_apg_done = True
        self._live_apg_current = self._live_apg_total or self._segment_files * 2
        self.message = "APG-MOS 已完成，等待 MultiPA…" if not self._live_multipa_done else "并行评测完成"
        await self._persist()

    async def sync_live_from_redis(self) -> None:
        live = await read_live_progress(self.job_id)
        if live:
            self.apply_live(live)
        await self._persist()

    async def tick_file(self, current: int, message: str = "") -> None:
        if message:
            self.message = message
        await self.sync_live_from_redis()

    async def finish(self, *, success: bool = True) -> None:
        await self._stop_ticker()
        self.phase = "done"
        self._live_multipa_done = True
        self._live_apg_done = True
        self._live_multipa_current = self._live_multipa_total or self._segment_files
        self._live_apg_current = self._live_apg_total or self._segment_files * 2
        self.message = "评测完成" if success else "评测失败"
        await self._persist()

    async def _start_ticker(self) -> None:
        await self._stop_ticker()
        self._ticker = asyncio.create_task(self._ticker_loop())

    async def _stop_ticker(self) -> None:
        if self._ticker and not self._ticker.done():
            self._ticker.cancel()
            try:
                await self._ticker
            except asyncio.CancelledError:
                pass
        self._ticker = None

    async def stop(self) -> None:
        await self._stop_ticker()

    async def _ticker_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(0.5)
                await self.sync_live_from_redis()
        except asyncio.CancelledError:
            pass


async def poll_live_progress(
    job_id: str,
    reporter: JobProgressReporter,
    stop: asyncio.Event,
) -> None:
    """评测 HTTP 阻塞期间轮询 Redis 实时进度。"""
    while not stop.is_set():
        try:
            live = await read_live_progress(job_id)
            if live:
                reporter.apply_live(live)
                await reporter._persist()
        except Exception:
            logger.debug("live progress poll failed for %s", job_id, exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.4)
            break
        except asyncio.TimeoutError:
            continue


def _detail_int(detail: dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        val = detail.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    return default


def _detail_bool(detail: dict[str, Any], *keys: str, default: bool = False) -> bool:
    for key in keys:
        val = detail.get(key)
        if val is not None:
            return bool(val)
    return default


def progress_detail_vo(detail: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not detail:
        return None
    phase_label = detail.get("phaseLabel") or detail.get("phase_label") or ""
    return {
        "phase": detail.get("phase"),
        "phaseLabel": phase_label,
        "current": _detail_int(detail, "current"),
        "total": _detail_int(detail, "total"),
        "multipaCurrent": _detail_int(detail, "multipaCurrent", "multipa_current"),
        "multipaTotal": _detail_int(detail, "multipaTotal", "multipa_total"),
        "apgCurrent": _detail_int(detail, "apgCurrent", "apg_current"),
        "apgTotal": _detail_int(detail, "apgTotal", "apg_total"),
        "multipaDone": _detail_bool(detail, "multipaDone", "multipa_done"),
        "apgDone": _detail_bool(detail, "apgDone", "apg_done"),
        "elapsedSec": detail.get("elapsedSec", detail.get("elapsed_sec")),
        "etaSec": detail.get("etaSec", detail.get("eta_sec")),
        "elapsedText": detail.get("elapsedText", detail.get("elapsed_text", "")),
        "etaText": detail.get("etaText", detail.get("eta_text", "")),
        "ratePerSec": detail.get("ratePerSec", detail.get("rate_per_sec")),
        "message": detail.get("message", ""),
        "tqdmLine": detail.get("tqdmLine", detail.get("tqdm_line", "")),
    }
