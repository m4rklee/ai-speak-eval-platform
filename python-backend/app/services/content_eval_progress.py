"""内容评测任务进度（Redis）。"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from app.db.redis import get_redis

JOB_KEY_PREFIX = "content_eval:job:"
JOB_TTL_SEC = 86400

# 每条约 20–30s（3 次 LLM 并行）
SEC_PER_FILE = 25.0


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def _format_duration(sec: float) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


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


class ContentEvalProgressReporter:
    def __init__(self, job_id: str, total_files: int, *, offset: int = 0) -> None:
        self.job_id = job_id
        self.total_files = max(1, total_files)
        self.offset = max(0, offset)
        self.started_at = time.time()
        self.current = offset
        self.message = ""

    def _build_detail(self) -> dict[str, Any]:
        elapsed = time.time() - self.started_at
        done = self.current - self.offset
        rate = done / elapsed if elapsed > 0 and done > 0 else 0
        remaining = self.total_files - self.current
        eta = remaining / rate if rate > 0 else remaining * SEC_PER_FILE
        pct = int(min(99, (self.current / self.total_files) * 100)) if self.current < self.total_files else 100
        elapsed_text = _format_duration(elapsed)
        eta_text = _format_duration(eta)
        tqdm_line = (
            f"内容评测 [{self.current}/{self.total_files}] "
            f"{pct}% | {elapsed_text}<{eta_text}"
        )
        if self.message:
            tqdm_line += f" | {self.message}"
        return {
            "phase": "evaluating",
            "phase_label": "内容评测",
            "current": self.current,
            "total": self.total_files,
            "elapsed_sec": round(elapsed, 1),
            "eta_sec": round(eta, 1),
            "elapsed_text": elapsed_text,
            "eta_text": eta_text,
            "rate_per_sec": round(rate, 3) if rate else None,
            "message": self.message,
            "tqdm_line": tqdm_line,
        }

    async def update(self, current: int, message: str = "") -> None:
        self.current = current
        self.message = message
        redis = get_redis()
        raw = await redis.get(_job_key(self.job_id))
        if not raw:
            return
        payload = json.loads(raw)
        detail = self._build_detail()
        progress = int(min(99, (current / self.total_files) * 100))
        payload["progress"] = progress
        payload["progress_detail"] = detail
        payload["status"] = "running"
        await redis.set(_job_key(self.job_id), json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SEC)

    async def finish(self, *, success: bool) -> None:
        redis = get_redis()
        raw = await redis.get(_job_key(self.job_id))
        if not raw:
            return
        payload = json.loads(raw)
        detail = self._build_detail()
        detail["phase"] = "done"
        detail["phase_label"] = "完成" if success else "失败"
        payload["progress"] = 100
        payload["progress_detail"] = detail
        await redis.set(_job_key(self.job_id), json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SEC)
