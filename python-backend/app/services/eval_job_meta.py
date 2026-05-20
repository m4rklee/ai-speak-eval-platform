"""评测任务元数据：显示名称、创建参数校验。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from app.core.errors import BusinessException, ErrorCode
from app.utils.model_id import split_model_id

TYPE_LABELS = {
    "listen": "听力",
    "oral_gen": "回复生成",
    "speech": "语音",
    "content": "内容",
    "combined": "综合",
}

DISPLAY_NAME_MAX = 64
EVAL_ROUNDS_MIN = 1
EVAL_ROUNDS_MAX = 5


def normalize_display_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(name).strip())
    if not cleaned:
        return None
    if len(cleaned) > DISPLAY_NAME_MAX:
        raise BusinessException(
            ErrorCode.PARAMS_ERROR,
            f"任务名称不能超过 {DISPLAY_NAME_MAX} 个字符",
        )
    return cleaned


def default_display_name(job_type: str, model: str = "") -> str:
    label = TYPE_LABELS.get(job_type, job_type)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    model_part = ""
    if model:
        _, vendor = split_model_id(model)
        model_part = vendor.split("/")[-1][:24] if vendor else model.split(":")[-1][:24]
    if model_part:
        return f"{label}-{model_part}-{now}"[:DISPLAY_NAME_MAX]
    return f"{label}-{now}"[:DISPLAY_NAME_MAX]


def resolve_display_name(
    job_type: str,
    model: str,
    requested: Optional[str],
) -> str:
    custom = normalize_display_name(requested)
    if custom:
        return custom
    return default_display_name(job_type, model)


def normalize_eval_rounds(value: Optional[int]) -> int:
    if value is None:
        return EVAL_ROUNDS_MIN
    n = int(value)
    if n < EVAL_ROUNDS_MIN or n > EVAL_ROUNDS_MAX:
        raise BusinessException(
            ErrorCode.PARAMS_ERROR,
            f"评测轮次须在 {EVAL_ROUNDS_MIN}–{EVAL_ROUNDS_MAX} 之间",
        )
    return n


def meta_vo(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "displayName": payload.get("display_name"),
        "evalRounds": int(payload.get("eval_rounds") or 1),
        "judgeModel": payload.get("judge_model"),
    }


def apply_create_meta(
    payload: dict[str, Any],
    *,
    job_type: str,
    model: str = "",
    display_name: Optional[str] = None,
    eval_rounds: Optional[int] = None,
    judge_model: Optional[str] = None,
) -> None:
    payload["display_name"] = resolve_display_name(job_type, model, display_name)
    payload["eval_rounds"] = normalize_eval_rounds(eval_rounds)
    if judge_model:
        payload["judge_model"] = judge_model.strip()


async def update_display_name(payload: dict[str, Any], display_name: str) -> None:
    payload["display_name"] = normalize_display_name(display_name)
    if not payload["display_name"]:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "任务名称不能为空")
