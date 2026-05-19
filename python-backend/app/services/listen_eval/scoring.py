"""北极星听力评测：从模型回复提取选项并聚合准确率。"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def canonicalize_text(value: Any) -> str:
    aliases = {
        "disguist": "disgust",
        "man": "male",
        "woman": "female",
        "middle aged adult": "middle-aged adult",
    }
    normalized = normalize_text(value)
    return aliases.get(normalized, normalized)


def extract_prediction(response_text: Any) -> str:
    if response_text is None:
        return ""

    text = str(response_text).strip().upper()
    if not text or text == "NONE":
        return ""

    if text[0] in "ABCDE":
        return text[0]

    matches = re.findall(r"(?<![A-Z])([A-E])(?![A-Z])", text)
    if matches:
        return matches[-1]

    if text[-1] in "ABCDE":
        return text[-1]

    return ""


def get_answer_label(record: dict[str, Any]) -> str:
    answer_label = str(record.get("answer_label", "")).strip().upper()
    if answer_label in {"A", "B", "C", "D", "E"}:
        return answer_label

    answer_gt = record.get("answer_gt", "")
    answer_gt_upper = str(answer_gt).strip().upper()
    if answer_gt_upper in {"A", "B", "C", "D", "E"}:
        return answer_gt_upper

    choices = {
        "A": record.get("choice_a", ""),
        "B": record.get("choice_b", ""),
        "C": record.get("choice_c", ""),
        "D": record.get("choice_d", ""),
        "E": record.get("choice_e", ""),
    }
    canonical_answer = canonicalize_text(answer_gt)
    for label, choice in choices.items():
        if canonicalize_text(choice) == canonical_answer:
            return label
    return ""


def _update_bucket(bucket: dict[str, int], is_correct: bool) -> None:
    bucket["total"] += 1
    if is_correct:
        bucket["correct"] += 1


def _finalize_bucket(bucket: dict[str, int]) -> dict[str, Any]:
    total = bucket["total"]
    correct = bucket["correct"]
    bucket["accuracy"] = correct / total if total else 0.0
    return bucket


def evaluate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    overall: dict[str, int] = {
        "correct": 0,
        "total": 0,
        "invalid_response": 0,
        "missing_answer": 0,
    }
    by_dimension: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    by_source_benchmark: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    by_source_dataset: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )

    for record in records:
        answer_label = get_answer_label(record)
        prediction = extract_prediction(record.get("response", ""))
        dimension = record.get("dimension") or record.get("task_name") or "unknown"
        source_benchmark = record.get("source_benchmark", "unknown")
        source_dataset = record.get("source_dataset", "unknown")

        overall["total"] += 1

        if not answer_label:
            overall["missing_answer"] += 1
            _update_bucket(by_dimension[dimension], False)
            _update_bucket(by_source_benchmark[source_benchmark], False)
            _update_bucket(by_source_dataset[source_dataset], False)
            continue

        if not prediction:
            overall["invalid_response"] += 1
            _update_bucket(by_dimension[dimension], False)
            _update_bucket(by_source_benchmark[source_benchmark], False)
            _update_bucket(by_source_dataset[source_dataset], False)
            continue

        is_correct = prediction == answer_label
        if is_correct:
            overall["correct"] += 1

        _update_bucket(by_dimension[dimension], is_correct)
        _update_bucket(by_source_benchmark[source_benchmark], is_correct)
        _update_bucket(by_source_dataset[source_dataset], is_correct)

    overall["accuracy"] = overall["correct"] / overall["total"] if overall["total"] else 0.0

    return {
        "overall": overall,
        "by_dimension": {
            key: _finalize_bucket(value) for key, value in sorted(by_dimension.items())
        },
        "by_source_benchmark": {
            key: _finalize_bucket(value)
            for key, value in sorted(by_source_benchmark.items())
        },
        "by_source_dataset": {
            key: _finalize_bucket(value)
            for key, value in sorted(by_source_dataset.items())
        },
    }


def enrich_result_row(record: dict[str, Any]) -> dict[str, Any]:
    """为单条推理结果附加 prediction / isCorrect 等字段。"""
    answer_label = get_answer_label(record)
    prediction = extract_prediction(record.get("response", ""))
    is_correct = bool(answer_label and prediction and prediction == answer_label)
    return {
        **record,
        "answerLabel": answer_label,
        "prediction": prediction,
        "isCorrect": is_correct if answer_label and prediction else None,
    }
