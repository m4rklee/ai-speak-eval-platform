"""口语内容评测：北极星三维方法（gpt_eval_new_dimensions ContentEvaluator）"""
from typing import Any

from app.services.oral_eval.content_dimensions import (
    DEFAULT_JUDGE_MODEL,
    evaluate_content_dimensions,
)


async def score_content(
    *,
    item_prompt: str,
    expected_answer: str,
    model_output: str,
    judge_model: str,
    rubric: str = "",
    max_score: int = 100,
) -> dict[str, Any]:
    """
    内容评分入口。rubric / max_score 保留兼容旧配置；
    实际评测逻辑与 gpt_eval_new_dimensions.py 中 ContentEvaluator 三维一致。
    expected_answer 当前不参与三维打分（与参考脚本 evaluate_all 一致，仅用 question+answer）。
    """
    _ = expected_answer, rubric, max_score
    result = await evaluate_content_dimensions(
        question=item_prompt or "",
        answer=model_output or "",
        judge_model=judge_model or DEFAULT_JUDGE_MODEL,
    )
    return result
