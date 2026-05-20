"""异步 Redis 任务断点续跑：活跃 worker 注册、中断标记、续跑校验。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.services.content_eval_progress import JOB_TTL_SEC

logger = logging.getLogger(__name__)

# 各模块 Redis job key 前缀（不含 job_id）
JOB_PREFIXES: tuple[str, ...] = (
    "listen_eval:job:",
    "oral_gen:job:",
    "content_eval:job:",
    "uni_eval:job:",
    "oral_combined:job:",
)

RESUMABLE_STATUSES = frozenset({"interrupted", "paused"})
COMBINED_RESUME_STATUSES = frozenset({"interrupted", "paused", "awaiting_eval"})

_ACTIVE_KEYS: set[str] = set()


def task_key(prefix: str, job_id: str) -> str:
    return f"{prefix}{job_id}"


def is_active(prefix: str, job_id: str) -> bool:
    return task_key(prefix, job_id) in _ACTIVE_KEYS


def register_active(prefix: str, job_id: str) -> None:
    _ACTIVE_KEYS.add(task_key(prefix, job_id))


def unregister_active(prefix: str, job_id: str) -> None:
    _ACTIVE_KEYS.discard(task_key(prefix, job_id))


def completed_count_from_payload(payload: dict[str, Any]) -> int:
    if payload.get("completed_count") is not None:
        return int(payload["completed_count"])
    for key in (
        "partial_records",
        "partial_rows",
        "partial_per_file_rows",
        "gen_rows",
        "partial_gen_rows",
        "partial_model_results",
    ):
        val = payload.get(key)
        if isinstance(val, list):
            return len(val)
    return 0


def can_resume_payload(payload: dict[str, Any], *, combined: bool = False) -> bool:
    status = payload.get("status") or ""
    allowed = COMBINED_RESUME_STATUSES if combined else RESUMABLE_STATUSES
    if status not in allowed:
        return False
    if status == "awaiting_eval":
        return bool(payload.get("work_dir") or payload.get("gen_rows"))
    if payload.get("items") or payload.get("gen_items") or payload.get("pairs"):
        return True
    if payload.get("work_dir") and payload.get("file_names"):
        return True
    if payload.get("job_type") == "multi_model" and payload.get("model_specs"):
        return True
    return completed_count_from_payload(payload) < int(payload.get("total_samples") or payload.get("total_files") or 0)


def resume_meta_vo(payload: dict[str, Any], *, combined: bool = False) -> dict[str, Any]:
    completed = completed_count_from_payload(payload)
    total = int(
        payload.get("total_samples")
        or payload.get("total_files")
        or payload.get("total")
        or 0
    )
    status = payload.get("status") or ""
    can = can_resume_payload(payload, combined=combined) and not is_active_for_payload(payload)
    return {
        "completedCount": completed,
        "totalCount": total,
        "canResume": can,
        "interruptedAt": payload.get("interrupted_at"),
        "pausedAt": payload.get("paused_at"),
        "hasCheckpoint": completed > 0,
    }


def is_active_for_payload(payload: dict[str, Any]) -> bool:
    job_id = payload.get("job_id", "")
    if not job_id:
        return False
    for prefix in JOB_PREFIXES:
        if is_active(prefix, job_id):
            return True
    return False


def assert_can_resume(
    payload: dict[str, Any],
    job_id: str,
    prefix: str,
    *,
    combined: bool = False,
) -> None:
    if is_active(prefix, job_id):
        raise BusinessException(ErrorCode.OPERATION_ERROR, "任务正在运行中")
    status = payload.get("status") or ""
    allowed = COMBINED_RESUME_STATUSES if combined else RESUMABLE_STATUSES
    if status not in allowed:
        raise BusinessException(
            ErrorCode.OPERATION_ERROR,
            f"任务状态为 {status}，无法续跑",
        )
    if status == "awaiting_eval":
        return
    if not (
        payload.get("items")
        or payload.get("gen_items")
        or payload.get("pairs")
        or payload.get("work_dir")
        or payload.get("model_specs")
    ):
        raise BusinessException(ErrorCode.OPERATION_ERROR, "任务输入数据已丢失，无法续跑")


async def mark_stale_jobs() -> int:
    """启动时将无 worker 的 pending/running 任务标为 interrupted。"""
    redis = get_redis()
    marked = 0
    now = datetime.now().isoformat(timespec="seconds")
    stale_statuses = frozenset({"pending", "running", "generating"})

    for prefix in JOB_PREFIXES:
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode()
                job_id = key[len(prefix) :]
                if is_active(prefix, job_id):
                    continue
                raw = await redis.get(key)
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                status = payload.get("status") or ""
                if status not in stale_statuses:
                    continue
                payload["status"] = "interrupted"
                payload["interrupted_at"] = now
                await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SEC)
                marked += 1
                logger.info("Marked stale job interrupted: %s (%s)", job_id, prefix)
            if cursor == 0:
                break

    if marked:
        logger.info("mark_stale_jobs: %d job(s) marked interrupted", marked)
    return marked


def wrap_task(prefix: str, job_id: str, coro: Any) -> asyncio.Task:
    """注册活跃任务并包装 coro，结束时 unregister。"""

    async def _runner() -> None:
        register_active(prefix, job_id)
        try:
            await coro
        finally:
            unregister_active(prefix, job_id)

    return asyncio.create_task(_runner())
