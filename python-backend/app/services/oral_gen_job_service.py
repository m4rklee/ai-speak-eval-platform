"""口语回复生成异步任务。"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.services.content_eval_progress import JOB_TTL_SEC, progress_detail_vo
from app.services.eval_job_meta import (
    apply_create_meta,
    meta_vo,
    update_display_name as apply_display_name,
)
from app.services.job_progress import (
    api_error_vo,
    append_warning_to_detail,
    record_row_error,
)
from app.services.job_control import (
    assert_can_pause,
    assert_can_rerun,
    check_pause_requested,
    control_meta_vo,
    prepare_rerun_payload,
    request_pause,
    save_input_snapshot,
)
from app.services.job_resume import assert_can_resume, resume_meta_vo, wrap_task
from app.services.token_aggregate import add_tokens_with_cost, ensure_estimated_cost, token_summary_vo
from app.services.oral_gen.questionwav import health_check, sample_items, stem_from_path
from app.services.oral_gen.runner import (
    generate_reply,
    persist_result,
    validate_api_configured,
)
from app.utils.model_id import normalize_model_id

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "oral_gen:job:"
USER_JOBS_PREFIX = "oral_gen:user:"
USER_JOB_LIST_MAX = 20
SEC_PER_ITEM = 25.0


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def _user_jobs_key(user_id: int) -> str:
    return f"{USER_JOBS_PREFIX}{user_id}:jobs"


def _job_dir(job_id: str) -> str:
    return os.path.join(get_settings().ORAL_GEN_OUTPUT_ROOT, job_id)


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


def _job_vo_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if summary and isinstance(summary, dict):
        summary = {**summary, **token_summary_vo(payload)}
    rows = payload.get("rows") or payload.get("partial_rows")
    meta = resume_meta_vo(payload)
    detail = append_warning_to_detail(payload.get("progress_detail"), payload)
    return {
        "jobId": payload.get("job_id", ""),
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalSamples": payload.get("total_samples", 0),
        "model": payload.get("model", ""),
        "source": payload.get("source", ""),
        "sampleMode": payload.get("sample_mode", ""),
        "error": payload.get("error"),
        "summary": summary,
        "rows": rows,
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(detail),
        **meta_vo(payload),
        **api_error_vo(payload),
        **token_summary_vo(payload),
        **meta,
        **control_meta_vo(payload, JOB_KEY_PREFIX, payload.get("job_id", "")),
    }


class _OralGenProgressReporter:
    def __init__(self, job_id: str, total: int, *, offset: int = 0) -> None:
        import time

        self.job_id = job_id
        self.total = max(1, total)
        self.offset = max(0, offset)
        self.started_at = time.time()
        self.current = offset
        self.message = ""

    def _build_detail(self) -> dict[str, Any]:
        import time

        elapsed = time.time() - self.started_at
        done = self.current - self.offset
        rate = done / elapsed if elapsed > 0 and done > 0 else 0
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
            f"回复生成 [{self.current}/{self.total}] "
            f"{pct}% | {elapsed_text}<{eta_text}"
        )
        if self.message:
            tqdm_line += f" | {self.message}"
        return {
            "phase": "generating",
            "phase_label": "模型生成",
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


class OralGenJobService:
    @staticmethod
    def health() -> dict[str, Any]:
        return health_check()

    @staticmethod
    async def create_job_builtin(
        user_id: int,
        *,
        model: str,
        sample_mode: Literal["all", "random"],
        sample_count: int = 0,
        seed: Optional[int] = None,
        request_interval: Optional[float] = None,
        display_name: Optional[str] = None,
        eval_rounds: Optional[int] = None,
    ) -> str:
        h = health_check()
        if not h.get("questionwav_dir_ok") or not h.get("wav_count"):
            raise BusinessException(
                ErrorCode.OPERATION_ERROR,
                h.get("message") or "内置音频数据集不可用",
            )
        validate_api_configured()

        settings = get_settings()
        try:
            items = sample_items(mode=sample_mode, count=sample_count, seed=seed)
        except (ValueError, FileNotFoundError) as e:
            raise BusinessException(ErrorCode.PARAMS_ERROR, str(e)) from e

        return await OralGenJobService._create_job_internal(
            user_id,
            model=model,
            source="builtin",
            sample_mode=sample_mode,
            items=items,
            request_interval=request_interval,
            display_name=display_name,
            eval_rounds=eval_rounds,
        )

    @staticmethod
    async def create_job_upload(
        user_id: int,
        *,
        model: str,
        files: list[UploadFile],
        request_interval: Optional[float] = None,
        display_name: Optional[str] = None,
        eval_rounds: Optional[int] = None,
    ) -> str:
        validate_api_configured()
        if not files:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请上传至少一个 wav 文件")

        settings = get_settings()
        max_n = settings.ORAL_GEN_MAX_SAMPLES_PER_JOB
        if len(files) > max_n:
            raise BusinessException(
                ErrorCode.PARAMS_ERROR,
                f"单次最多 {max_n} 个文件",
            )

        job_id = uuid.uuid4().hex
        input_dir = os.path.join(_job_dir(job_id), "input")
        os.makedirs(input_dir, exist_ok=True)
        items: list[dict[str, Any]] = []
        for uf in files:
            name = (uf.filename or "audio.wav").replace("/", "_").replace("\\", "_")
            if not name.lower().endswith(".wav"):
                name = f"{stem_from_path(name)}.wav"
            dest = os.path.join(input_dir, name)
            content = await uf.read()
            if not content:
                continue
            with open(dest, "wb") as f:
                f.write(content)
            items.append({"stem": stem_from_path(name), "path": dest})

        if not items:
            shutil.rmtree(_job_dir(job_id), ignore_errors=True)
            raise BusinessException(ErrorCode.PARAMS_ERROR, "无有效 wav 文件")

        return await OralGenJobService._create_job_internal(
            user_id,
            model=model,
            source="upload",
            sample_mode="upload",
            items=items,
            request_interval=request_interval,
            existing_job_id=job_id,
            display_name=display_name,
            eval_rounds=eval_rounds,
        )

    @staticmethod
    async def _create_job_internal(
        user_id: int,
        *,
        model: str,
        source: str,
        sample_mode: str,
        items: list[dict[str, Any]],
        request_interval: Optional[float],
        existing_job_id: Optional[str] = None,
        display_name: Optional[str] = None,
        eval_rounds: Optional[int] = None,
    ) -> str:
        settings = get_settings()
        job_id = existing_job_id or uuid.uuid4().hex
        job_root = _job_dir(job_id)
        os.makedirs(os.path.join(job_root, "text"), exist_ok=True)
        os.makedirs(os.path.join(job_root, "audio"), exist_ok=True)

        interval = (
            request_interval
            if request_interval is not None
            else settings.ORAL_GEN_REQUEST_INTERVAL_SEC
        )
        interval = max(0.0, float(interval))
        normalized_model = normalize_model_id(model)
        now = datetime.now().isoformat(timespec="seconds")

        payload = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",
            "progress": 0,
            "total_samples": len(items),
            "model": normalized_model,
            "source": source,
            "sample_mode": sample_mode,
            "request_interval": interval,
            "items": items,
            "partial_rows": [],
            "completed_count": 0,
            "created_at": now,
            "finished_at": None,
            "error": None,
            "summary": None,
            "rows": None,
            "api_error_count": 0,
        }
        apply_create_meta(
            payload,
            job_type="oral_gen",
            model=normalized_model,
            display_name=display_name,
            eval_rounds=eval_rounds,
        )
        save_input_snapshot(
            payload,
            items=items,
            model=normalized_model,
            source=source,
            sample_mode=sample_mode,
            request_interval=interval,
            total_samples=len(items),
            eval_rounds=payload.get("eval_rounds"),
            display_name=payload.get("display_name"),
        )
        await _save_job(job_id, payload)
        await _push_user_job(user_id, job_id)
        wrap_task(JOB_KEY_PREFIX, job_id, OralGenJobService._run_job(job_id, interval))
        return job_id

    @staticmethod
    async def resume_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_resume(payload, job_id, JOB_KEY_PREFIX)
        if not payload.get("items"):
            raise BusinessException(ErrorCode.OPERATION_ERROR, "题目列表已丢失，无法续跑")
        payload["status"] = "running"
        payload["error"] = None
        await _save_job(job_id, payload)
        interval = float(payload.get("request_interval") or 0)
        wrap_task(JOB_KEY_PREFIX, job_id, OralGenJobService._run_job(job_id, interval))

    @staticmethod
    async def pause_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_pause(payload, job_id, JOB_KEY_PREFIX)
        request_pause(payload)
        await _save_job(job_id, payload)

    @staticmethod
    async def rerun_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_rerun(payload, job_id, JOB_KEY_PREFIX)
        prepare_rerun_payload(payload)
        await _save_job(job_id, payload)
        interval = float(payload.get("request_interval") or 0)
        wrap_task(JOB_KEY_PREFIX, job_id, OralGenJobService._run_job(job_id, interval))

    @staticmethod
    async def _run_job(job_id: str, interval: float) -> None:
        payload = await _load_job(job_id)
        if not payload:
            return

        items: list[dict[str, Any]] = payload.get("items") or []
        model = payload.get("model", "")
        eval_rounds = int(payload.get("eval_rounds") or 1)
        job_root = _job_dir(job_id)
        total = len(items)
        total_units = max(1, total * eval_rounds)
        rows_vo: list[dict[str, Any]] = list(payload.get("partial_rows") or [])
        start_idx = len(rows_vo)
        units_done = start_idx * eval_rounds
        ok_count = sum(1 for r in rows_vo if not r.get("error"))
        fail_count = len(rows_vo) - ok_count
        reporter = _OralGenProgressReporter(job_id, total_units, offset=units_done)

        if start_idx > 0:
            await reporter.update(units_done, message="续跑中…")

        try:
            paused = False
            for idx in range(start_idx, total):
                item = items[idx]
                stem = str(item.get("stem", ""))[:48]
                wav_path = item.get("path", "")
                last_raw: dict[str, Any] = {}
                for rnd in range(eval_rounds):
                    unit = idx * eval_rounds + rnd
                    await reporter.update(unit, message=f"{stem} · 第{rnd + 1}/{eval_rounds}轮")
                    last_raw = await generate_reply(model, wav_path)
                    payload = await _load_job(job_id) or payload
                    await add_tokens_with_cost(
                        payload,
                        int(last_raw.get("inputTokens") or 0),
                        int(last_raw.get("outputTokens") or 0),
                    )
                    await _save_job(job_id, payload)
                    await reporter.update(unit + 1, message=stem)
                    if interval > 0 and (rnd + 1 < eval_rounds or idx + 1 < total):
                        await asyncio.sleep(interval)
                vo = persist_result(job_root, last_raw)
                record_row_error(payload, vo)
                rows_vo.append(vo)
                if vo.get("error"):
                    fail_count += 1
                else:
                    ok_count += 1
                payload = await _load_job(job_id) or payload
                payload["partial_rows"] = rows_vo
                payload["completed_count"] = len(rows_vo)
                await _save_job(job_id, payload)
                if await check_pause_requested(_load_job, job_id, payload):
                    paused = True
                    break

            if paused:
                return

            await reporter.finish(success=True)
            payload = await _load_job(job_id) or payload
            payload["status"] = "completed"
            payload["progress"] = 100
            payload["summary"] = {
                "total": total,
                "success": ok_count,
                "failed": fail_count,
            }
            payload["rows"] = rows_vo
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            payload.pop("items", None)
            payload.pop("partial_rows", None)
            payload.pop("completed_count", None)
        except Exception as e:
            logger.exception("Oral gen job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = int(min(99, (len(rows_vo) / max(1, total)) * 100))
            payload["error"] = str(e)[:500]
            payload["partial_rows"] = rows_vo
            payload["completed_count"] = len(rows_vo)
            payload["rows"] = rows_vo
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

    @staticmethod
    async def assert_job_access(job_id: str, user_id: int) -> dict[str, Any]:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        return payload

    @staticmethod
    async def build_export_zip(job_id: str, user_id: int) -> bytes:
        await OralGenJobService.assert_job_access(job_id, user_id)
        root = _job_dir(job_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for sub in ("text", "audio"):
                subdir = os.path.join(root, sub)
                if not os.path.isdir(subdir):
                    continue
                for name in sorted(os.listdir(subdir)):
                    full = os.path.join(subdir, name)
                    if os.path.isfile(full):
                        zf.write(full, arcname=f"{sub}/{name}")
        buf.seek(0)
        return buf.getvalue()
