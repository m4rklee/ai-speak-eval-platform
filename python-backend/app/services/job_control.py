"""评测任务暂停 / 重跑：共享控制逻辑。"""
from __future__ import annotations

import copy
import os
from datetime import datetime
from typing import Any, Optional

from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.services.job_resume import is_active

PAUSABLE_STATUSES = frozenset({"pending", "running", "generating"})
RERUN_BLOCKED_STATUSES = frozenset({"pending", "running", "generating"})
RERUN_ALLOWED_STATUSES = frozenset({"paused", "interrupted", "failed", "completed", "awaiting_eval"})

PARTIAL_KEYS = (
    "partial_records",
    "partial_rows",
    "partial_per_file_rows",
    "partial_per_file_entries",
    "partial_gen_rows",
    "gen_rows",
    "partial_model_results",
    "model_cursor",
    "rows",
    "per_file_rows",
    "result",
)

RESULT_KEYS = (
    "summary",
    "error",
    "finished_at",
    "interrupted_at",
    "paused_at",
    "pause_requested",
    "audio_dir",
)

TOKEN_KEYS = (
    "total_input_tokens",
    "total_output_tokens",
    "estimated_cost_usd",
    "api_error_count",
    "last_api_error",
    "last_api_error_at",
)


def eval_job_input_dir(job_id: str) -> str:
    root = get_settings().EVAL_JOB_DATA_ROOT.strip() or "/root/autodl-tmp/eval_job_data"
    return os.path.join(root, job_id, "input")


SNAPSHOT_SOURCE_KEYS = (
    "items",
    "gen_items",
    "pairs",
    "file_names",
    "model_specs",
    "work_dir",
    "model",
    "models",
    "job_type",
    "sample_mode",
    "sample_count",
    "seed",
    "request_interval",
    "workers",
    "eval_rounds",
    "judge_model",
    "display_name",
    "total_samples",
    "total_files",
    "total",
    "model_count",
    "oral_gen_job_id",
    "pipeline_mode",
    "gen_model",
    "speech_engine",
    "source",
)


def ensure_input_snapshot(payload: dict[str, Any]) -> bool:
    """若缺失 input_snapshot，尝试从 payload 现有字段回填（兼容升级前任务）。"""
    if payload.get("input_snapshot"):
        return True
    snap: dict[str, Any] = {}
    for key in SNAPSHOT_SOURCE_KEYS:
        val = payload.get(key)
        if val is not None:
            snap[key] = copy.deepcopy(val)
    if not snap:
        return False
    payload["input_snapshot"] = snap
    return True


def has_rerun_input(payload: dict[str, Any]) -> bool:
    ensure_input_snapshot(payload)
    snap = payload.get("input_snapshot") or {}
    if snap.get("items") or snap.get("pairs") or snap.get("gen_items"):
        return True
    if snap.get("model_specs"):
        wd = snap.get("work_dir")
        return bool(wd and os.path.isdir(wd))
    wd = snap.get("work_dir")
    names = snap.get("file_names")
    if wd and names and os.path.isdir(wd):
        return True
    return False


def control_meta_vo(payload: dict[str, Any], prefix: str, job_id: str) -> dict[str, Any]:
    status = payload.get("status") or ""
    active = is_active(prefix, job_id)
    pause_requested = bool(payload.get("pause_requested"))
    return {
        "pausedAt": payload.get("paused_at"),
        "pauseRequested": pause_requested,
        "canPause": status in PAUSABLE_STATUSES and not pause_requested,
        "canRerun": status in RERUN_ALLOWED_STATUSES and not active and has_rerun_input(payload),
    }


def assert_can_pause(payload: dict[str, Any], job_id: str, prefix: str) -> None:
    status = payload.get("status") or ""
    if status not in PAUSABLE_STATUSES:
        raise BusinessException(ErrorCode.OPERATION_ERROR, f"任务状态为 {status}，无法暂停")
    if payload.get("pause_requested"):
        raise BusinessException(ErrorCode.OPERATION_ERROR, "暂停请求已提交，请稍候")


def execute_pause(payload: dict[str, Any], prefix: str, job_id: str) -> None:
    """发起暂停：有 worker 时置 flag 等待 checkpoint；无 worker（僵尸 running）则立即 paused。"""
    assert_can_pause(payload, job_id, prefix)
    if is_active(prefix, job_id):
        request_pause(payload)
    else:
        apply_pause(payload)


def assert_can_rerun(payload: dict[str, Any], job_id: str, prefix: str) -> None:
    status = payload.get("status") or ""
    if status in RERUN_BLOCKED_STATUSES:
        raise BusinessException(ErrorCode.OPERATION_ERROR, "任务运行中，请先暂停后再重跑")
    if is_active(prefix, job_id):
        raise BusinessException(ErrorCode.OPERATION_ERROR, "任务正在运行中，请先暂停")
    if status not in RERUN_ALLOWED_STATUSES:
        raise BusinessException(ErrorCode.OPERATION_ERROR, f"任务状态为 {status}，无法重跑")
    if not has_rerun_input(payload):
        raise BusinessException(
            ErrorCode.OPERATION_ERROR,
            "任务输入快照已丢失，无法重跑（升级前创建且输入已清理的任务请新建任务）",
        )


def request_pause(payload: dict[str, Any]) -> None:
    payload["pause_requested"] = True


def apply_pause(payload: dict[str, Any]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    payload["pause_requested"] = False
    payload["status"] = "paused"
    payload["paused_at"] = now


async def check_pause_requested(load_job, job_id: str, payload: dict[str, Any]) -> bool:
    """Worker 在 checkpoint 边界调用；若用户请求暂停则更新 payload 并返回 True。"""
    fresh = await load_job(job_id)
    if not fresh:
        return False
    if fresh.get("pause_requested"):
        apply_pause(fresh)
        payload.clear()
        payload.update(fresh)
        return True
    return False


def save_input_snapshot(payload: dict[str, Any], **fields: Any) -> None:
    """创建任务时保存不可变输入快照，供重跑恢复。"""
    snap: dict[str, Any] = {}
    for key, val in fields.items():
        if val is not None:
            snap[key] = copy.deepcopy(val)
    payload["input_snapshot"] = snap


def apply_runtime_options(
    payload: dict[str, Any],
    *,
    workers: Optional[int] = None,
    request_interval: Optional[float] = None,
) -> None:
    """续跑 / 重跑前更新并发与间隔，并同步到 input_snapshot。"""
    if workers is not None:
        payload["workers"] = max(1, min(16, int(workers)))
    if request_interval is not None:
        payload["request_interval"] = max(0.0, float(request_interval))
    snap = payload.get("input_snapshot")
    if isinstance(snap, dict):
        if workers is not None:
            snap["workers"] = payload["workers"]
        if request_interval is not None:
            snap["request_interval"] = payload["request_interval"]


def has_partial_progress(payload: dict[str, Any]) -> bool:
    for key in PARTIAL_KEYS:
        val = payload.get(key)
        if isinstance(val, list) and val:
            return True
        if isinstance(val, dict) and val:
            return True
    return int(payload.get("completed_count") or 0) > 0


def prepare_rerun_payload(payload: dict[str, Any], *, skip_completed: bool = False) -> None:
    """就地重置 payload 以重跑（调用方需先 assert_can_rerun）。"""
    ensure_input_snapshot(payload)
    snapshot: dict[str, Any] = copy.deepcopy(payload.get("input_snapshot") or {})

    keep_partial = skip_completed and has_partial_progress(payload)
    keys_to_clear: list[str] = list(RESULT_KEYS)
    if not keep_partial:
        keys_to_clear += list(PARTIAL_KEYS) + list(TOKEN_KEYS)

    for key in keys_to_clear:
        payload.pop(key, None)

    partial_len = len(payload.get("partial_records") or [])
    if keep_partial:
        payload["progress"] = int(
            min(99, (partial_len / max(1, int(payload.get("total_samples") or 1))) * 100)
        ) if partial_len else 0
        payload["completed_count"] = partial_len
    else:
        payload["progress"] = 0
        payload["completed_count"] = 0
    payload["status"] = "pending"
    payload["error"] = None
    payload["finished_at"] = None
    payload["interrupted_at"] = None
    payload["paused_at"] = None
    payload["pause_requested"] = False

    restore_keys = (
        "items",
        "gen_items",
        "pairs",
        "file_names",
        "model_specs",
        "work_dir",
        "model",
        "models",
        "job_type",
        "sample_mode",
        "sample_count",
        "seed",
        "request_interval",
        "workers",
        "eval_rounds",
        "judge_model",
        "display_name",
        "total_samples",
        "total_files",
        "total",
        "model_count",
        "oral_gen_job_id",
        "pipeline_mode",
        "gen_model",
        "speech_engine",
        "source",
    )
    for key in restore_keys:
        if key in snapshot:
            payload[key] = copy.deepcopy(snapshot[key])

    if payload.get("work_dir"):
        wd = payload["work_dir"]
        if not os.path.isdir(wd):
            raise BusinessException(
                ErrorCode.OPERATION_ERROR,
                "任务输入文件目录已丢失，无法重跑",
            )
