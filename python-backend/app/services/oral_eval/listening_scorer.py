"""听力评测：模型文本输出 vs 标准答案"""
import re
from typing import Any


def normalize_text(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[\s\u3000]+", " ", t)
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", "", t)
    return t.strip()


def score_listening(
    output_text: str,
    expected_answer: str,
    mode: str = "normalized_match",
) -> dict[str, Any]:
    out_n = normalize_text(output_text)
    exp_n = normalize_text(expected_answer)
    if not exp_n:
        return {
            "score": 0.0,
            "match": False,
            "method": mode,
            "reason": "标准答案为空",
        }
    if not out_n:
        return {
            "score": 0.0,
            "match": False,
            "method": mode,
            "reason": "模型无文本输出",
        }

    if out_n == exp_n:
        return {"score": 1.0, "match": True, "method": mode, "reason": "完全匹配"}

    if exp_n in out_n or out_n in exp_n:
        ratio = min(len(out_n), len(exp_n)) / max(len(out_n), len(exp_n), 1)
        return {
            "score": round(0.7 + 0.3 * ratio, 4),
            "match": ratio >= 0.6,
            "method": mode,
            "reason": "包含关系匹配",
        }

    # 字符级 Jaccard 相似度
    set_o, set_e = set(out_n), set(exp_n)
    inter = len(set_o & set_e)
    union = len(set_o | set_e) or 1
    jaccard = inter / union
    return {
        "score": round(jaccard, 4),
        "match": jaccard >= 0.5,
        "method": mode,
        "reason": f"相似度 {jaccard:.2%}",
    }
