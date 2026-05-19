"""
口语内容评测：北极星数据集三维方法（源自 gpt_eval_new_dimensions.py ContentEvaluator）

维度：
- 语法准确表达（0-100）
- 主题聚焦拓展（0-4）
- 回复简洁清晰（0-3，取 JSON 综合评分）
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from app.providers.registry import get_provider
from app.utils.model_id import normalize_model_id, split_model_id, vendor_model_id

logger = logging.getLogger(__name__)

DEFAULT_JUDGE_MODEL = "aihubmix:gemini-3.1-flash-lite"


def extract_json(feedback: str) -> dict[str, Any]:
    """从 API 返回内容中提取 JSON（与参考脚本 _extract_json 一致）"""
    if not feedback or not feedback.strip():
        return {"error": "空响应"}

    try:
        return json.loads(feedback)
    except json.JSONDecodeError:
        pass

    if "{" in feedback:
        start_idx = feedback.find("{")
        open_braces = 0
        close_braces = 0
        json_end_idx = -1
        for i in range(start_idx, len(feedback)):
            if feedback[i] == "{":
                open_braces += 1
            elif feedback[i] == "}":
                close_braces += 1
                if open_braces == close_braces:
                    json_end_idx = i
                    break
        if json_end_idx != -1:
            json_str = feedback[start_idx : json_end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    json_matches = re.findall(r"({(?:[^{}]|(?:{[^{}]*}))*})", feedback, re.DOTALL)
    for match in json_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    key_patterns = [
        r'({[^{}]*"错误数量"[^{}]*})',
        r'({[^{}]*"综合评分"[^{}]*})',
        r'({[^{}]*"主题聚焦拓展分数"[^{}]*})',
        r'({[^{}]*"回复简洁清晰分数"[^{}]*})',
    ]
    for pattern in key_patterns:
        for match in re.findall(pattern, feedback, re.DOTALL):
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    return {"error": "无法提取有效的JSON数据"}


def _clean_grammar_text(text: str) -> str:
    text = text.encode("utf-8").decode("utf-8")
    return re.sub(r"[^\x00-\x7F]+", "", text)


def _calculate_grammar_accuracy(sentence: str, error_count: float) -> float:
    word_count = len(sentence.split())
    if word_count == 0:
        return 1.0
    if error_count == 0:
        return 1.0
    if word_count <= 10:
        length_penalty = 1.0
    elif word_count <= 20:
        length_penalty = 0.9
    else:
        length_penalty = 0.8
    if error_count > 2:
        penalty_decrease = (error_count - 2) / 10 * (0.8 - 0.4)
        length_penalty = max(0.5, length_penalty - penalty_decrease)
    error_ratio = error_count / word_count
    return max(0, (1 - error_ratio) * length_penalty)


def _grammar_level(score: float) -> str:
    if score < 50:
        return "非常差"
    if score < 70:
        return "差"
    if score < 85:
        return "一般"
    if score < 95:
        return "好"
    return "非常好"


async def _call_judge_llm(prompt: str, judge_model: str, max_retries: int = 3) -> str:
    model_id = normalize_model_id(judge_model or DEFAULT_JUDGE_MODEL)
    platform, _ = split_model_id(model_id)
    vendor_id = vendor_model_id(model_id)
    provider = get_provider(platform)
    backoff = 1.0
    last_err: Optional[Exception] = None
    for retry in range(max_retries):
        try:
            result = await provider.chat_completion(
                vendor_id,
                [{"role": "user", "content": prompt}],
                max_tokens=4000,
                timeout=120.0,
            )
            return (result.text or "").strip()
        except Exception as e:
            last_err = e
            logger.warning(
                "内容评测 API 失败 (%s/%s): %s",
                retry + 1,
                max_retries,
                e,
            )
            if retry < max_retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
    raise last_err or RuntimeError("内容评测 API 调用失败")


async def evaluate_grammar(answer: str, judge_model: str) -> dict[str, Any]:
    if not answer or not isinstance(answer, str):
        return {"error": "无效输入", "score": 0}

    sentence = _clean_grammar_text(answer)
    prompt = (
        f"请作为一个专业的英语语法检测工具，对以下句子进行详细的语法检查：\n\n"
        f"句子：{sentence}\n\n"
        f"分析句子内容是否包含语法错误，分析句子结构、词汇用法、拼写错误以及标点符号是否符合语法规范等内容。"
        f"请务必给出详细的报告，包括所有发现的错误类型及其数量。即使没有发现错误，也请确认并说明没有检测到错误。"
        f"注意，只需指出与语法相关的错误，如动词时态错误、主谓一致错误、动词形式错误、冠词错误、词汇选择错误、标点符号错误和句子结构错误、顺序错误等,也关注是否存在更为标准或惯用的表达方式，例如不定式表达等"
        f"请严格以这样的形式输出，下面是一个输出例子： \n\n"
        f"待评测句子: This are a example of bad grammar sentence.\n"
        f"错误数量:X\n"
        f"总单词数:Y\n"
        f"错误详情:\n"
        f"- 主谓不一致: Z\n"
        f"- 时态错误: W\n"
        f"- 语序错误: V\n"
        f"确保反馈中每一行都严格遵循上述格式，以便于解析。\n"
    )
    feedback = await _call_judge_llm(prompt, judge_model)
    match = re.search(r"错误数量:\s*(\d+)", feedback)
    error_count = float(match.group(1)) if match else 0.0
    accuracy = _calculate_grammar_accuracy(sentence, error_count)
    score = accuracy * 100
    return {
        "sentence": sentence,
        "error_count": error_count,
        "accuracy": round(accuracy, 6),
        "score": round(score, 2),
        "level": _grammar_level(score),
        "dim_name_cn": "语法准确表达",
        "dim_name_en": "Grammar Accuracy",
    }


async def evaluate_theme_focus(question: str, answer: str, judge_model: str) -> dict[str, Any]:
    if not answer or not isinstance(answer, str):
        return {"error": "无效输入", "主题聚焦拓展分数": 0}

    prompt = (
        f"   - 问题：{question}\n"
        f"   - 回答：{answer}\n"
        """
            # 角色设定
            你是一名口语对话质量评估专家，需要评估以上对话的回答是否围绕给定的主题，并判断是否对其进行了合理的拓展延伸。请根据以下评分标准对每个回答进行五级的评分：

            # 评分标准
            非常差(0分)：回答完全偏离主题(相关度<20%)，无任何有帮助的拓展信息。
            差(1分)：回答主题相关度低(20%至50%)，仅开头/结尾点题，提供的拓展信息无实质内容或与主题无关。
            一般(2分)：回答基本相关(相关度50%至70%)，有一些偏离，仅重复主题关键词或提供了1个基础细节。
            好(3分)：回答紧密相关(相关度70%至90%)，最多有1句轻微偏离，提供了1个相关细节且有一定深度。
            非常好(4分)：回答完全契合主题(相关度>90%)，所有内容直接相关，提供了多个(≥2)有深度的相关细节，拓展合理且有连贯性。

            # 说明
            - 引导性提问不应简单被视为偏离主题，而应作为拓展的一部分评估：紧密相关的引导性提问（直接针对主题或前述内容）应被视为有效拓展，开放式提问应根据其与主题的相关性评估。

            # 评测步骤
            1. **输入问题与回答**：接收[问题]和[回答]。
            2. **评分**：根据上述标准给出0-4分的主题聚焦拓展能力等级。
            3. **给出简要理由**：用1-2句话说明评分理由。

            # 输出格式为json格式，必须严格遵守json格式规范，不要添加多余文字，直接输出json对象。例如下面示例
            {
                "问题": "...",
                "回答": "...",
                "主题聚焦拓展分数": 4,
                "评分理由": "..."
            }
            """
    )
    feedback = await _call_judge_llm(prompt, judge_model)
    return extract_json(feedback)


async def evaluate_answer_clarity(question: str, answer: str, judge_model: str) -> dict[str, Any]:
    if not answer or not isinstance(answer, str):
        return {"error": "无效输入", "综合评分": 0}

    prompt = (
        f"   - 问题：{question}\n"
        f"   - 回答：{answer}\n"
        """
            # 角色设定
你是一名英语口语教育评测专家，需要严格评估以上输入的回答在“回复简洁清晰”维度上的表现，判断其是否适合作为初中学生口语练习场景中的模型回复。
你只关注回答本身，不评测问题的质量。
你的任务是从**表达简洁清晰**和**提问控制合理**两个维度分析回答，并判断其是否符合口语练习场景中“易懂、不冗长、不过度追问”的要求。

# 评估维度
## 1. 表达简洁清晰
- **回复是否简洁**：回答是否聚焦当前问题，不过度展开，不堆砌无关信息，不出现明显冗余表达？
- **回复是否清晰易懂**：表达是否直接明确、层次清楚，便于初中学生快速理解，不使用过于绕弯或含混的表述？
- **是否不过度表达**：是否存在明显的过量解释、重复说明、额外延伸太多内容，导致学生抓不住重点？

## 2. 提问控制合理
- **问题数量是否适中**：单轮回答中提出的问题数量是否不过多，不会给学生造成较大作答负担？
- **问题长度是否适中**：如果回答中包含追问，问题本身是否简短清楚，不过长不过绕？
- **是否便于学生继续回应**：追问是否自然、聚焦，能够帮助学生继续表达，而不是连续抛出多个复杂问题？

# 评测步骤
1. **获取对话**：获取输入的问题与模型回答的对话数据。
2. **分析回答**：对模型的回答按上述维度分析是否符合“回复简洁清晰”的要求，并指出具体问题。每个子维度符合要求则+1分，总分为0-3分。
3. **综合判断**：给出综合评分，为“表达简洁清晰分数”和“提问控制合理分数”的平均值，范围为0-3分。

# 评分标准补充说明
- 如果回答内容整体简洁、重点明确、没有明显冗余，且追问数量少、长度适中，则应给高分。
- 如果回答虽然基本相关，但存在解释过多、重复啰嗦、追问过多或问题太长，则应酌情扣分。
- 如果回答明显冗长、重点不清、一次性提出多个复杂问题，增加学生理解和回应负担，则应给低分。

# 输出格式为json格式，必须严格遵守json格式规范，不要添加多余文字，直接输出json对象。例如下面示例

{
"对话": [
    {"问题": "...",
     "回答": "..."}
],
"表达简洁清晰分析": {
    "回复简洁": {"是否符合": true, "问题描述": "..."},
    "回复清晰易懂": {"是否符合": true, "问题描述": "..."},
    "不过度表达": {"是否符合": true, "问题描述": "..."},
    "表达简洁清晰分数": 3
},
"提问控制合理分析": {
    "问题数量": {"是否符合": true, "问题描述": "..."},
    "问题长度": {"是否符合": true, "问题描述": "..."},
    "便于继续回应": {"是否符合": true, "问题描述": "..."},
    "提问控制合理分数": 3
},
"综合评分": 3
}
"""
    )
    feedback = await _call_judge_llm(prompt, judge_model)
    return extract_json(feedback)


def _dimension_scores_for_composite(
    grammar: dict[str, Any],
    theme: dict[str, Any],
    clarity: dict[str, Any],
) -> list[float]:
    """三维归一化到 0-100 后取平均（与参考脚本 evaluate_all 思路一致）"""
    scores: list[float] = []
    if isinstance(grammar.get("score"), (int, float)):
        scores.append(float(grammar["score"]))
    theme_score = theme.get("主题聚焦拓展分数")
    if isinstance(theme_score, (int, float)):
        scores.append(float(theme_score) / 4.0 * 100.0)
    clarity_score = clarity.get("综合评分")
    if clarity_score is None:
        clarity_score = clarity.get("回复简洁清晰分数")
    if isinstance(clarity_score, (int, float)):
        scores.append(float(clarity_score) / 3.0 * 100.0)
    return scores


def _build_reason(
    grammar: dict[str, Any],
    theme: dict[str, Any],
    clarity: dict[str, Any],
) -> str:
    parts = []
    if grammar.get("score") is not None:
        parts.append(f"语法 {grammar['score']}（{grammar.get('level', '')}）")
    if theme.get("主题聚焦拓展分数") is not None:
        parts.append(f"主题聚焦 {theme['主题聚焦拓展分数']}/4")
    if clarity.get("综合评分") is not None:
        parts.append(f"简洁清晰 {clarity['综合评分']}/3")
    theme_reason = theme.get("评分理由")
    if theme_reason:
        parts.append(str(theme_reason)[:200])
    return "；".join(parts) if parts else "三维评测完成"


async def evaluate_content_dimensions(
    *,
    question: str,
    answer: str,
    judge_model: str,
) -> dict[str, Any]:
    """运行语法 / 主题聚焦 / 回复简洁清晰三维评测，返回统一结构。"""
    if not (answer or "").strip():
        return {
            "status": "ok",
            "method": "gpt_eval_new_dimensions",
            "score": 0,
            "max": 100,
            "composite": 0,
            "reason": "无文本输出",
            "dimensions": {},
        }

    grammar, theme, clarity = await asyncio.gather(
        evaluate_grammar(answer, judge_model),
        evaluate_theme_focus(question, answer, judge_model),
        evaluate_answer_clarity(question, answer, judge_model),
    )

    norm_scores = _dimension_scores_for_composite(grammar, theme, clarity)
    composite = round(sum(norm_scores) / len(norm_scores), 2) if norm_scores else 0.0

    return {
        "status": "ok",
        "method": "gpt_eval_new_dimensions",
        "score": composite,
        "max": 100,
        "composite": composite,
        "reason": _build_reason(grammar, theme, clarity),
        "judgeModel": normalize_model_id(judge_model or DEFAULT_JUDGE_MODEL),
        "dimensions": {
            "grammar": grammar,
            "themeFocus": theme,
            "answerClarity": clarity,
        },
        "dimensionScores": {
            "语法准确表达": grammar.get("score"),
            "主题聚焦拓展": theme.get("主题聚焦拓展分数"),
            "回复简洁清晰": clarity.get("综合评分") or clarity.get("回复简洁清晰分数"),
        },
    }
