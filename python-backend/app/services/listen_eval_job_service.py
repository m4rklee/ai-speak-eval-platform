"""北极星 2201 听力评测异步任务。"""
from __future__ import annotations

import asyncio
import copy
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
from app.services.eval_job_meta import (
    apply_create_meta,
    meta_vo,
    update_display_name as apply_display_name,
)
from app.services.eval_rounds import aggregate_listen_rounds
from app.services.job_progress import (
    api_error_vo,
    append_warning_to_detail,
    record_row_error,
)
from app.services.job_control import (
    assert_can_pause,
    assert_can_rerun,
    apply_runtime_options,
    check_pause_requested,
    control_meta_vo,
    prepare_rerun_payload,
    execute_pause,
    save_input_snapshot,
    ensure_input_snapshot,
)
from app.services.job_resume import (
    assert_can_resume,
    resume_meta_vo,
    wrap_task,
)
from app.services.listen_eval.runner import infer_item, validate_model_configured
from app.services.token_aggregate import add_tokens_with_cost, ensure_estimated_cost, token_summary_vo
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
    if not per_file and payload.get("partial_records"):
        per_file = [_row_to_vo(r) for r in payload["partial_records"]]
    meta = resume_meta_vo(payload)
    detail = append_warning_to_detail(payload.get("progress_detail"), payload)
    return {
        "jobId": payload.get("job_id", ""),
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalSamples": payload.get("total_samples", 0),
        "model": payload.get("model", ""),
        "sampleMode": payload.get("sample_mode", ""),
        "workers": payload.get("workers"),
        "requestInterval": payload.get("request_interval"),
        "error": payload.get("error"),
        "summary": summary,
        "perFile": per_file,
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(detail),
        **meta_vo(payload),
        **api_error_vo(payload),
        **token_summary_vo(payload),
        **meta,
        **control_meta_vo(payload, JOB_KEY_PREFIX, payload.get("job_id", "")),
    }


class _ListenProgressReporter:
    def __init__(self, job_id: str, total: int, *, offset: int = 0) -> None:
        self.job_id = job_id
        self.total = max(1, total)
        self.offset = max(0, offset)
        self.started_at = time.time()
        self.current = offset
        self.message = ""

    def _build_detail(self) -> dict[str, Any]:
        elapsed = time.time() - self.started_at
        rate = (self.current - self.offset) / elapsed if elapsed > 0 and self.current > self.offset else 0
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
        display_name: Optional[str] = None,
        eval_rounds: Optional[int] = None,
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
        worker_count = max(1, min(16, int(worker_count)))

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
            "partial_records": [],
            "completed_count": 0,
            "created_at": now,
            "finished_at": None,
            "error": None,
            "summary": None,
            "per_file_rows": None,
            "api_error_count": 0,
        }
        apply_create_meta(
            payload,
            job_type="listen",
            model=normalized_model,
            display_name=display_name,
            eval_rounds=eval_rounds,
        )
        save_input_snapshot(
            payload,
            items=items,
            model=normalized_model,
            sample_mode=sample_mode,
            sample_count=sample_count if sample_mode == "random" else len(items),
            seed=seed,
            request_interval=interval,
            workers=worker_count,
            total_samples=len(items),
            eval_rounds=payload.get("eval_rounds"),
            display_name=payload.get("display_name"),
        )
        await _save_job(job_id, payload)
        await _push_user_job(user_id, job_id)
        wrap_task(
            JOB_KEY_PREFIX,
            job_id,
            ListenEvalJobService._run_job(job_id, interval, worker_count),
        )
        return job_id

    @staticmethod
    async def resume_job(
        user_id: int,
        job_id: str,
        *,
        workers: Optional[int] = None,
        request_interval: Optional[float] = None,
    ) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_resume(payload, job_id, JOB_KEY_PREFIX)
        if not payload.get("items"):
            ensure_input_snapshot(payload)
            snap = payload.get("input_snapshot") or {}
            if snap.get("items"):
                payload["items"] = copy.deepcopy(snap["items"])
        if not payload.get("items"):
            raise BusinessException(ErrorCode.OPERATION_ERROR, "题目列表已丢失，无法续跑")

        apply_runtime_options(payload, workers=workers, request_interval=request_interval)
        payload["status"] = "running"
        payload["error"] = None
        await _save_job(job_id, payload)
        interval = float(payload.get("request_interval") or 0)
        worker_count = int(payload.get("workers") or 1)
        wrap_task(
            JOB_KEY_PREFIX,
            job_id,
            ListenEvalJobService._run_job(job_id, interval, worker_count),
        )

    @staticmethod
    async def pause_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        execute_pause(payload, JOB_KEY_PREFIX, job_id)
        await _save_job(job_id, payload)

    @staticmethod
    async def rerun_job(
        user_id: int,
        job_id: str,
        *,
        workers: Optional[int] = None,
        request_interval: Optional[float] = None,
        skip_completed: bool = False,
    ) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_rerun(payload, job_id, JOB_KEY_PREFIX)
        prepare_rerun_payload(payload, skip_completed=skip_completed)
        apply_runtime_options(payload, workers=workers, request_interval=request_interval)
        await _save_job(job_id, payload)
        interval = float(payload.get("request_interval") or 0)
        worker_count = int(payload.get("workers") or 1)
        wrap_task(
            JOB_KEY_PREFIX,
            job_id,
            ListenEvalJobService._run_job(job_id, interval, worker_count),
        )

    @staticmethod
    async def _run_item(
        model: str,
        item: dict[str, Any],
        *,
        eval_rounds: int,
        sem: asyncio.Semaphore,
        interval: float,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        round_rows: list[dict[str, Any]] = []
        for rnd in range(eval_rounds):
            async with sem:
                row = await infer_item(model, item)
            round_rows.append(row)
            if interval > 0 and rnd + 1 < eval_rounds:
                await asyncio.sleep(interval)
        return round_rows, aggregate_listen_rounds(round_rows)

    @staticmethod
    async def _apply_item_result(
        job_id: str,
        payload: dict[str, Any],
        *,
        item_idx: int,
        slot_records: list[Optional[dict[str, Any]]],
        round_rows: list[dict[str, Any]],
        agg: dict[str, Any],
        payload_lock: asyncio.Lock,
    ) -> dict[str, Any]:
        async with payload_lock:
            payload = await _load_job(job_id) or payload
            for row in round_rows:
                await add_tokens_with_cost(
                    payload,
                    int(row.get("input_tokens") or 0),
                    int(row.get("output_tokens") or 0),
                )
            record_row_error(payload, agg)
            slot_records[item_idx] = agg
            contiguous: list[dict[str, Any]] = []
            for row in slot_records:
                if row is None:
                    break
                contiguous.append(row)
            payload["partial_records"] = contiguous
            payload["completed_count"] = len(contiguous)
            await _save_job(job_id, payload)
            return payload

    @staticmethod
    async def _run_job(job_id: str, interval: float, workers: int) -> None:
        payload = await _load_job(job_id)
        if not payload:
            return

        items: list[dict[str, Any]] = payload.get("items") or []
        model = payload.get("model", "")
        eval_rounds = int(payload.get("eval_rounds") or 1)
        total = len(items)
        total_units = max(1, total * eval_rounds)
        records: list[dict[str, Any]] = list(payload.get("partial_records") or [])
        start_idx = len(records)
        units_done = start_idx * eval_rounds
        reporter = _ListenProgressReporter(job_id, total_units, offset=units_done)
        sem = asyncio.Semaphore(workers)
        payload_lock = asyncio.Lock()
        slot_records: list[Optional[dict[str, Any]]] = [None] * total
        for i, row in enumerate(records):
            if i < total:
                slot_records[i] = row

        if start_idx >= total and total > 0:
            records = records[:total]
        elif start_idx > 0:
            await reporter.update(units_done, message="续跑中…")

        in_flight: set[asyncio.Task[tuple[int, list[dict[str, Any]], dict[str, Any]]]] = set()
        next_idx = start_idx
        units_completed = units_done
        paused = False

        async def _launch() -> None:
            nonlocal next_idx
            while next_idx < total and len(in_flight) < workers:
                idx = next_idx
                next_idx += 1
                item = items[idx]

                async def _work(
                    item_idx: int,
                    work_item: dict[str, Any],
                ) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
                    round_rows, agg = await ListenEvalJobService._run_item(
                        model,
                        work_item,
                        eval_rounds=eval_rounds,
                        sem=sem,
                        interval=interval,
                    )
                    return item_idx, round_rows, agg

                task = asyncio.create_task(_work(idx, item))
                in_flight.add(task)
                task.add_done_callback(in_flight.discard)

        try:
            while next_idx < total or in_flight:
                payload = await _load_job(job_id) or payload
                if await check_pause_requested(_load_job, job_id, payload):
                    paused = True
                    for task in list(in_flight):
                        task.cancel()
                    if in_flight:
                        await asyncio.gather(*in_flight, return_exceptions=True)
                    break

                await _launch()
                if not in_flight:
                    break

                done, _pending = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    if task.cancelled():
                        continue
                    exc = task.exception()
                    if exc is not None:
                        raise exc
                    item_idx, round_rows, agg = task.result()
                    item_id = str(items[item_idx].get("id", ""))[:48]
                    units_completed += len(round_rows)
                    payload = await ListenEvalJobService._apply_item_result(
                        job_id,
                        payload,
                        item_idx=item_idx,
                        slot_records=slot_records,
                        round_rows=round_rows,
                        agg=agg,
                        payload_lock=payload_lock,
                    )
                    await reporter.update(
                        units_completed,
                        message=f"{item_id} ({units_completed}/{total_units})",
                    )

            if paused:
                return

            records = [row for row in slot_records if row is not None]
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
            payload.pop("partial_records", None)
            payload.pop("completed_count", None)
        except Exception as e:
            logger.exception("Listen eval job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            contiguous = [row for row in slot_records if row is not None]
            payload["status"] = "failed"
            payload["progress"] = int(min(99, (len(contiguous) / max(1, total)) * 100))
            payload["partial_records"] = contiguous
            payload["completed_count"] = len(contiguous)
            payload["error"] = str(e)[:500]
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
        finally:
            await _save_job(job_id, payload)

    @staticmethod
    async def get_job(job_id: str, user_id: int) -> dict[str, Any]:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看该任务")
        if ensure_input_snapshot(payload):
            await _save_job(job_id, payload)
        await ensure_estimated_cost(payload)
        if payload.get("estimated_cost_usd") is not None:
            await _save_job(job_id, payload)
        return _job_vo_from_payload(payload)

    @staticmethod
    async def update_display_name(user_id: int, job_id: str, display_name: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        await apply_display_name(payload, display_name)
        await _save_job(job_id, payload)

    @staticmethod
    async def list_jobs(user_id: int) -> list[dict[str, Any]]:
        redis = get_redis()
        job_ids = await redis.lrange(_user_jobs_key(user_id), 0, USER_JOB_LIST_MAX - 1)
        out: list[dict[str, Any]] = []
        for jid in job_ids:
            payload = await _load_job(jid)
            if payload:
                await ensure_estimated_cost(payload)
                out.append(_job_vo_from_payload(payload))
        return out
