"""北极星 2201 听力评测异步任务。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.services.content_eval_progress import JOB_TTL_SEC, progress_detail_vo
from app.services.listen_eval.runner import infer_item, validate_model_configured
from app.services.listen_eval.scoring import enrich_result_row, evaluate_records
from app.utils.listen_eval_benchmark import health_check, sample_items
from app.utils.model_id import normalize_model_id

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "listen_eval:job:"
USER_JOBS_PREFIX = "listen_eval:user:"
USER_JOB_LIST_MAX = 20

SEC_PER_ITEM = 8.0


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def _user_jobs_key(user_id: int) -> str:
    return f"{USER_JOBS_PREFIX}{user_id}:jobs"


async def _save_job(job_id: str, payload: dict[str, Any]) -> None:
    redis = get_redis()
    await redis.set(_job_key(job_id), json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SEC)


async def _load_job(job_id: str) -> Optional[dict[str, Any]]:
    redis = get_redis()
    raw = await redis.get(_job_key(job_id))
    if not raw:
        return None
    return json.loads(raw)


async def _push_user_job(user_id: int, job_id: str) -> None:
    redis = get_redis()
    key = _user_jobs_key(user_id)
    await redis.lrem(key, 0, job_id)
    await redis.lpush(key, job_id)
    await redis.ltrim(key, 0, USER_JOB_LIST_MAX - 1)
    await redis.expire(key, JOB_TTL_SEC)


def _format_duration(sec: float) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _row_to_vo(record: dict[str, Any]) -> dict[str, Any]:
    enriched = enrich_result_row(record)
    return {
        "id": enriched.get("id", ""),
        "question": enriched.get("question", ""),
        "choiceA": enriched.get("choice_a", ""),
        "choiceB": enriched.get("choice_b", ""),
        "choiceC": enriched.get("choice_c", ""),
        "choiceD": enriched.get("choice_d", ""),
        "choiceE": enriched.get("choice_e", ""),
        "dimension": enriched.get("dimension") or enriched.get("task_name", ""),
        "sourceDataset": enriched.get("source_dataset", ""),
        "prediction": enriched.get("prediction", ""),
        "answerLabel": enriched.get("answerLabel", ""),
        "isCorrect": enriched.get("isCorrect"),
        "response": enriched.get("response", ""),
        "error": enriched.get("error"),
    }


def _summary_to_vo(summary: dict[str, Any]) -> dict[str, Any]:
    overall = summary.get("overall") or {}
    return {
        "overall": overall,
        "byDimension": summary.get("by_dimension") or {},
        "bySourceBenchmark": summary.get("by_source_benchmark") or {},
        "bySourceDataset": summary.get("by_source_dataset") or {},
    }


def _job_vo_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if summary and "by_dimension" in summary:
        summary = _summary_to_vo(summary)
    per_file = payload.get("per_file_rows")
    return {
        "jobId": payload.get("job_id", ""),
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalSamples": payload.get("total_samples", 0),
        "model": payload.get("model", ""),
        "sampleMode": payload.get("sample_mode", ""),
        "error": payload.get("error"),
        "summary": summary,
        "perFile": per_file,
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(payload.get("progress_detail")),
    }


class _ListenProgressReporter:
    def __init__(self, job_id: str, total: int) -> None:
        self.job_id = job_id
        self.total = max(1, total)
        self.started_at = time.time()
        self.current = 0
        self.message = ""

    def _build_detail(self) -> dict[str, Any]:
        elapsed = time.time() - self.started_at
        rate = self.current / elapsed if elapsed > 0 and self.current > 0 else 0
        remaining = self.total - self.current
        eta = remaining / rate if rate > 0 else remaining * SEC_PER_ITEM
        pct = (
            int(min(99, (self.current / self.total) * 100))
            if self.current < self.total
            else 100
        )
        elapsed_text = _format_duration(elapsed)
        eta_text = _format_duration(eta)
        tqdm_line = (
            f"听力评测 [{self.current}/{self.total}] "
            f"{pct}% | {elapsed_text}<{eta_text}"
        )
        if self.message:
            tqdm_line += f" | {self.message}"
        return {
            "phase": "inferring",
            "phase_label": "听力推理",
            "current": self.current,
            "total": self.total,
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
        progress = int(min(99, (current / self.total) * 100)) if current < self.total else 99
        payload["progress"] = progress
        payload["progress_detail"] = self._build_detail()
        payload["status"] = "running"
        await _save_job(self.job_id, payload)

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
        await _save_job(self.job_id, payload)


class ListenEvalJobService:
    @staticmethod
    def health() -> dict[str, Any]:
        return health_check()

    @staticmethod
    async def create_job(
        user_id: int,
        *,
        model: str,
        sample_mode: Literal["all", "random"],
        sample_count: int = 0,
        seed: Optional[int] = None,
        request_interval: Optional[float] = None,
        workers: Optional[int] = None,
    ) -> str:
        h = health_check()
        if not h.get("benchmarkOk"):
            raise BusinessException(
                ErrorCode.OPERATION_ERROR,
                h.get("message") or "听力题库不可用",
            )
        validate_model_configured()

        settings = get_settings()
        try:
            items = sample_items(mode=sample_mode, count=sample_count, seed=seed)
        except (ValueError, FileNotFoundError) as e:
            raise BusinessException(ErrorCode.PARAMS_ERROR, str(e)) from e

        if not items:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "无可用题目")

        normalized_model = normalize_model_id(model)
        interval = (
            request_interval
            if request_interval is not None
            else settings.LISTEN_EVAL_REQUEST_INTERVAL_SEC
        )
        interval = max(0.0, float(interval))
        worker_count = workers if workers is not None else settings.LISTEN_EVAL_JOB_WORKERS
        worker_count = max(1, min(8, int(worker_count)))

        job_id = uuid.uuid4().hex
        now = datetime.now().isoformat(timespec="seconds")
        payload = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",
            "progress": 0,
            "total_samples": len(items),
            "model": normalized_model,
            "sample_mode": sample_mode,
            "sample_count": sample_count if sample_mode == "random" else len(items),
            "seed": seed,
            "request_interval": interval,
            "workers": worker_count,
            "items": items,
            "created_at": now,
            "finished_at": None,
            "error": None,
            "summary": None,
            "per_file_rows": None,
        }
        await _save_job(job_id, payload)
        await _push_user_job(user_id, job_id)
        asyncio.create_task(
            ListenEvalJobService._run_job(job_id, interval, worker_count)
        )
        return job_id

    @staticmethod
    async def _run_one(
        model: str,
        item: dict[str, Any],
        sem: asyncio.Semaphore,
    ) -> dict[str, Any]:
        async with sem:
            return await infer_item(model, item)

    @staticmethod
    async def _run_job(job_id: str, interval: float, workers: int) -> None:
        payload = await _load_job(job_id)
        if not payload:
            return

        items: list[dict[str, Any]] = payload.get("items") or []
        model = payload.get("model", "")
        total = len(items)
        reporter = _ListenProgressReporter(job_id, total)
        records: list[dict[str, Any]] = []
        sem = asyncio.Semaphore(workers)

        try:
            for idx, item in enumerate(items, start=1):
                item_id = str(item.get("id", ""))[:48]
                await reporter.update(idx - 1, message=item_id)
                row = await ListenEvalJobService._run_one(model, item, sem)
                records.append(row)
                await reporter.update(idx, message=item_id)
                if interval > 0 and idx < total:
                    await asyncio.sleep(interval)

            summary_raw = evaluate_records(records)
            rows_vo = [_row_to_vo(r) for r in records]
            await reporter.finish(success=True)
            payload = await _load_job(job_id) or payload
            payload["status"] = "completed"
            payload["progress"] = 100
            payload["summary"] = summary_raw
            payload["per_file_rows"] = rows_vo
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            payload.pop("items", None)
        except Exception as e:
            logger.exception("Listen eval job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = 100
            payload["error"] = str(e)[:500]
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            payload.pop("items", None)
        finally:
            await _save_job(job_id, payload)

    @staticmethod
    async def get_job(job_id: str, user_id: int) -> dict[str, Any]:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看该任务")
        return _job_vo_from_payload(payload)

    @staticmethod
    async def list_jobs(user_id: int) -> list[dict[str, Any]]:
        redis = get_redis()
        job_ids = await redis.lrange(_user_jobs_key(user_id), 0, USER_JOB_LIST_MAX - 1)
        out: list[dict[str, Any]] = []
        for jid in job_ids:
            payload = await _load_job(jid)
            if payload:
                out.append(_job_vo_from_payload(payload))
        return out
