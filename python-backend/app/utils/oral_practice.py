"""K-12 口语练习：消息构建与默认配置"""
from typing import Any, Optional

from app.core.config import get_settings
from app.schemas.conversation import AudioInput

DEFAULT_TEACHER_SYSTEM_PROMPT = (
    "You are a friendly teacher having a casual conversation with a middle school student. "
    "Answer the question in this audio naturally, using vocabulary and explanations appropriate "
    "for middle school level. Provide a thoughtful and brief response - about 2-3 sentences or "
    "10-20 seconds when spoken. Avoid using bullet points, numbered lists unless specifically asked for."
)

DEFAULT_EVAL_CONFIG: dict[str, Any] = {
    "listening": {"enabled": True, "mode": "normalized_match"},
    "pronunciation": {
        "enabled": True,
        "provider": "unified",
        "baseUrl": "",
        "refTextFrom": "output_content",
    },
    "contentJudge": {
        "enabled": True,
        "judgeModel": "",
        "maxScore": 5,
        "rubric": (
            "Evaluate whether the model's spoken response (as text transcript) appropriately addresses "
            "the student's audio question for a middle-school oral practice context. "
            "Score 1-5 for content quality, appropriateness, and alignment with the reference answer."
        ),
    },
    "weights": {"listening": 0.35, "pronunciation": 0.35, "content": 0.3},
}


def default_system_prompt() -> str:
    settings = get_settings()
    custom = getattr(settings, "ORAL_EVAL_DEFAULT_SYSTEM_PROMPT", "") or ""
    return custom.strip() or DEFAULT_TEACHER_SYSTEM_PROMPT


def default_eval_config() -> dict[str, Any]:
    settings = get_settings()
    cfg = {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_EVAL_CONFIG.items()}
    judge = getattr(settings, "ORAL_EVAL_JUDGE_MODEL", "") or ""
    if judge:
        cfg["contentJudge"]["judgeModel"] = judge
    pron_url = getattr(settings, "PRONUNCIATION_EVAL_URL", "") or ""
    if pron_url:
        cfg["pronunciation"]["baseUrl"] = pron_url
        cfg["pronunciation"]["provider"] = "http"
    elif getattr(settings, "UNIFIED_EVAL_ENABLED", True):
        cfg["pronunciation"]["provider"] = "unified"
    return cfg


def build_oral_practice_messages(
    audio_inputs: list[AudioInput],
    *,
    system_prompt: Optional[str] = None,
    user_message_mode: str = "audio_only",
    item_prompt: Optional[str] = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    sys_text = (system_prompt or "").strip() or default_system_prompt()
    messages.append({"role": "system", "content": sys_text})

    if user_message_mode == "audio_only":
        content: list[dict[str, Any]] = [
            {
                "type": "input_audio",
                "input_audio": {"data": a.data, "format": a.format},
            }
            for a in audio_inputs
        ]
    else:
        content = [{"type": "text", "text": item_prompt or "请处理这段音频"}]
        content.extend(
            {
                "type": "input_audio",
                "input_audio": {"data": a.data, "format": a.format},
            }
            for a in audio_inputs
        )
    messages.append({"role": "user", "content": content})
    return messages
