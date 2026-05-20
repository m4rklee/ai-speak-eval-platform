"""任务进度公共字段：API 错误追踪、VO 映射。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def record_api_error(payload: dict[str, Any], message: Optional[str]) -> None:
    """在 Redis payload 上记录一次 API/评测错误（就地修改）。"""
    if not message:
        return
    msg = str(message).strip()[:300]
    if not msg:
        return
    payload["api_error_count"] = int(payload.get("api_error_count") or 0) + 1
    payload["last_api_error"] = msg
    payload["last_api_error_at"] = datetime.now().isoformat(timespec="seconds")


def record_row_error(payload: dict[str, Any], row: dict[str, Any]) -> None:
    """从结果行提取 error/reason 并记录。"""
    err = row.get("error") or row.get("reason")
    if err and (row.get("status") in (None, "error", "failed") or row.get("error")):
        record_api_error(payload, str(err))


def append_warning_to_detail(detail: Optional[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    """在 progress_detail 中追加 warningLine。"""
    detail = dict(detail or {})
    count = int(payload.get("api_error_count") or 0)
    if count <= 0:
        detail.pop("warning_line", None)
        detail.pop("warningLine", None)
        return detail
    last = payload.get("last_api_error") or ""
    line = f"API/评测错误 {count} 条"
    if last:
        line += f" · 最近: {last[:120]}"
    detail["warning_line"] = line
    return detail


def api_error_vo(payload: dict[str, Any]) -> dict[str, Any]:
    count = int(payload.get("api_error_count") or 0)
    return {
        "apiErrorCount": count,
        "lastApiError": payload.get("last_api_error"),
        "lastApiErrorAt": payload.get("last_api_error_at"),
    }
