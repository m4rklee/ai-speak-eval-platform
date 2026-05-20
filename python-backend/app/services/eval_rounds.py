"""多轮评测结果聚合。"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Optional

from app.services.listen_eval.scoring import enrich_result_row, evaluate_records


def aggregate_listen_rounds(round_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """多轮听力推理：多数表决 prediction，保留 rounds 明细。"""
    if not round_rows:
        return {}
    if len(round_rows) == 1:
        base = dict(round_rows[0])
        enriched = enrich_result_row(base)
        return {**base, **{k: v for k, v in enriched.items() if k not in base}}

    base = dict(round_rows[0])
    preds = [
        str(r.get("prediction") or "").strip().upper()
        for r in round_rows
        if r.get("prediction")
    ]
    if preds:
        base["prediction"] = Counter(preds).most_common(1)[0][0]
    tin = sum(int(r.get("input_tokens") or 0) for r in round_rows)
    tout = sum(int(r.get("output_tokens") or 0) for r in round_rows)
    base["input_tokens"] = tin
    base["output_tokens"] = tout
    base["rounds"] = len(round_rows)
    enriched = enrich_result_row(base)
    return {**base, **{k: v for k, v in enriched.items() if k not in base}}


def aggregate_content_eval_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """多轮内容评测：维度分数取平均。"""
    if not results:
        return {}
    if len(results) == 1:
        return results[0]

    def _avg(key_path: tuple[str, ...]) -> Optional[float]:
        vals: list[float] = []
        for r in results:
            cur: Any = r
            for k in key_path:
                if not isinstance(cur, dict):
                    cur = None
                    break
                cur = cur.get(k)
            if isinstance(cur, (int, float)):
                vals.append(float(cur))
        return round(mean(vals), 2) if vals else None

    last = results[-1]
    dims = last.get("dimensions") or {}
    grammar = dict(dims.get("grammar") or {})
    theme = dict(dims.get("themeFocus") or {})
    clarity = dict(dims.get("answerClarity") or {})

    if grammar:
        s = _avg(("dimensions", "grammar", "score"))
        if s is not None:
            grammar["score"] = s
    if theme:
        s = _avg(("dimensions", "themeFocus", "主题聚焦拓展分数"))
        if s is not None:
            theme["主题聚焦拓展分数"] = s
    if clarity:
        s = _avg(("dimensions", "answerClarity", "综合评分"))
        if s is None:
            s = _avg(("dimensions", "answerClarity", "回复简洁清晰分数"))
        if s is not None:
            clarity["综合评分"] = s

    tin = sum(int(r.get("inputTokens") or 0) for r in results)
    tout = sum(int(r.get("outputTokens") or 0) for r in results)
    composites = [
        float(r.get("composite") or r.get("score") or 0)
        for r in results
        if isinstance(r.get("composite") or r.get("score"), (int, float))
    ]
    composite = round(mean(composites), 2) if composites else 0.0

    return {
        **last,
        "composite": composite,
        "score": composite,
        "inputTokens": tin,
        "outputTokens": tout,
        "rounds": len(results),
        "dimensions": {
            "grammar": grammar,
            "themeFocus": theme,
            "answerClarity": clarity,
        },
    }


def aggregate_speech_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """多轮语音 daemon per_file 条目：multipa 三维度与 apg_mos bvcc/somos 取平均。"""
    if not rows:
        return {}
    if len(rows) == 1:
        return dict(rows[0])

    base = dict(rows[0])
    mp_clean: dict[str, float] = {}
    for k in ("发音准确性", "流利度", "韵律"):
        vals: list[float] = []
        for r in rows:
            m = r.get("multipa") or {}
            if isinstance(m, dict) and isinstance(m.get(k), (int, float)):
                vals.append(float(m[k]))
        if vals:
            mp_clean[k] = round(mean(vals), 4)
    if mp_clean:
        base["multipa"] = mp_clean

    apg_vals: dict[str, list[float]] = {}
    for r in rows:
        apg = r.get("apg_mos") or {}
        if isinstance(apg, dict):
            for k in ("bvcc", "somos"):
                if isinstance(apg.get(k), (int, float)):
                    apg_vals.setdefault(k, []).append(float(apg[k]))
    if apg_vals:
        base["apg_mos"] = {k: round(mean(vs), 4) for k, vs in apg_vals.items()}
    base["rounds"] = len(rows)
    return base
