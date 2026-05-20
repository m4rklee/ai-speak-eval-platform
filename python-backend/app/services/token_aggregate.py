"""评测任务 Token 与费用汇总。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.model import Model
from app.utils.cost_calculator import CostCalculator
from app.utils.model_id import normalize_model_id


def _row_tokens(row: dict[str, Any]) -> tuple[int, int]:
    inp = row.get("input_tokens") or row.get("inputTokens") or 0
    out = row.get("output_tokens") or row.get("outputTokens") or 0
    return int(inp or 0), int(out or 0)


def sum_rows_tokens(rows: list[dict[str, Any]]) -> tuple[int, int]:
    total_in, total_out = 0, 0
    for row in rows:
        i, o = _row_tokens(row)
        total_in += i
        total_out += o
    return total_in, total_out


def add_tokens(payload: dict[str, Any], input_tokens: int, output_tokens: int) -> None:
    payload["total_input_tokens"] = int(payload.get("total_input_tokens") or 0) + int(input_tokens or 0)
    payload["total_output_tokens"] = int(payload.get("total_output_tokens") or 0) + int(output_tokens or 0)


def pricing_model_id(payload: dict[str, Any]) -> str:
    """根据任务 payload 推断用于计费的模型 ID。"""
    model = (payload.get("model") or "").strip()
    if model:
        return normalize_model_id(model)
    judge = (payload.get("judge_model") or "").strip()
    if judge:
        return normalize_model_id(judge)
    return normalize_model_id(get_settings().ORAL_EVAL_JUDGE_MODEL)


async def refresh_estimated_cost(payload: dict[str, Any]) -> None:
    tin = int(payload.get("total_input_tokens") or 0)
    tout = int(payload.get("total_output_tokens") or 0)
    if tin <= 0 and tout <= 0:
        return
    model_id = pricing_model_id(payload)
    if not model_id:
        return
    async with AsyncSessionLocal() as db:
        model = await db.get(Model, model_id)
    if not model:
        return
    cost = estimate_cost_usd(
        model_id,
        tin,
        tout,
        input_price=model.input_price,
        output_price=model.output_price,
    )
    if cost is not None:
        payload["estimated_cost_usd"] = cost


async def add_tokens_with_cost(
    payload: dict[str, Any],
    input_tokens: int,
    output_tokens: int,
) -> None:
    add_tokens(payload, input_tokens, output_tokens)
    await refresh_estimated_cost(payload)


async def ensure_estimated_cost(payload: dict[str, Any]) -> None:
    if payload.get("estimated_cost_usd") is not None:
        return
    await refresh_estimated_cost(payload)


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    input_price: Optional[Any] = None,
    output_price: Optional[Any] = None,
) -> Optional[float]:
    if input_price is None and output_price is None:
        return None
    if input_tokens <= 0 and output_tokens <= 0:
        return None
    cost = CostCalculator.calculate_cost(
        model,
        input_tokens,
        output_tokens,
        input_price,
        output_price,
    )
    return float(cost)


def token_summary_vo(payload: dict[str, Any]) -> dict[str, Any]:
    tin = int(payload.get("total_input_tokens") or 0)
    tout = int(payload.get("total_output_tokens") or 0)
    cost = payload.get("estimated_cost_usd")
    return {
        "totalInputTokens": tin,
        "totalOutputTokens": tout,
        "estimatedCostUsd": float(cost) if cost is not None else None,
    }


def build_token_summary(
    rows: list[dict[str, Any]],
    *,
    model: str = "",
    input_price: Optional[Any] = None,
    output_price: Optional[Any] = None,
) -> dict[str, Any]:
    tin, tout = sum_rows_tokens(rows)
    cost = estimate_cost_usd(model, tin, tout, input_price=input_price, output_price=output_price)
    out: dict[str, Any] = {
        "totalInputTokens": tin,
        "totalOutputTokens": tout,
    }
    if cost is not None:
        out["estimatedCostUsd"] = cost
    return out
