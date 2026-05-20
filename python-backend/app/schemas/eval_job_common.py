"""评测任务公共 schema（显示名、轮次、Token、API 错误）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EvalJobDisplayNameUpdateVO(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=64, alias="displayName")

    model_config = {"populate_by_name": True}


class EvalJobCreateMetaVO(BaseModel):
    """创建任务时可选元数据（JSON body 或 Form 字段）。"""

    display_name: Optional[str] = Field(default=None, alias="displayName")
    eval_rounds: Optional[int] = Field(default=None, alias="evalRounds", ge=1, le=5)
    judge_model: Optional[str] = Field(default=None, alias="judgeModel")

    model_config = {"populate_by_name": True}


class EvalJobTokenSummaryVO(BaseModel):
    total_input_tokens: int = Field(default=0, alias="totalInputTokens")
    total_output_tokens: int = Field(default=0, alias="totalOutputTokens")
    estimated_cost_usd: Optional[float] = Field(default=None, alias="estimatedCostUsd")

    model_config = {"populate_by_name": True}


class EvalJobApiErrorVO(BaseModel):
    api_error_count: int = Field(default=0, alias="apiErrorCount")
    last_api_error: Optional[str] = Field(default=None, alias="lastApiError")
    last_api_error_at: Optional[str] = Field(default=None, alias="lastApiErrorAt")

    model_config = {"populate_by_name": True}


class EvalJobControlVO(BaseModel):
    paused_at: Optional[str] = Field(default=None, alias="pausedAt")
    can_pause: Optional[bool] = Field(default=None, alias="canPause")
    can_rerun: Optional[bool] = Field(default=None, alias="canRerun")

    model_config = {"populate_by_name": True}


class EvalJobRuntimeOptionsVO(BaseModel):
    """续跑 / 重跑时可覆盖的运行参数。"""

    workers: Optional[int] = Field(default=None, ge=1, le=16)
    request_interval: Optional[float] = Field(default=None, ge=0, le=30, alias="requestInterval")
    skip_completed: Optional[bool] = Field(default=None, alias="skipCompleted")

    model_config = {"populate_by_name": True}
