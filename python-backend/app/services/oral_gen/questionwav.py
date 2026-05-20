"""内置 questionwav 数据集扫描与抽样。"""
from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any, Literal, Optional

from app.core.config import get_settings


def questionwav_dir() -> str:
    return get_settings().ORAL_GEN_QUESTIONWAV_DIR.strip() or "/root/autodl-tmp/questionwav"


def health_check() -> dict[str, Any]:
    settings = get_settings()
    root = questionwav_dir()
    root_ok = os.path.isdir(root)
    wav_count = 0
    if root_ok:
        wav_count = len(list_wav_paths(root))
    openrouter_ok = bool(settings.OPENROUTER_API_KEY.strip())
    aihubmix_ok = bool(settings.AIHUBMIX_API_KEY.strip())
    api_ok = openrouter_ok or aihubmix_ok
    ready = root_ok and wav_count > 0 and api_ok
    msg_parts: list[str] = []
    if not root_ok:
        msg_parts.append(f"内置音频目录不存在: {root}")
    elif wav_count == 0:
        msg_parts.append("内置音频目录无 .wav 文件")
    if not api_ok:
        msg_parts.append("未配置 OpenRouter 或 AiHubMix API Key")
    return {
        "questionwav_dir_ok": root_ok,
        "questionwav_dir": root,
        "wav_count": wav_count,
        "openrouter_configured": openrouter_ok,
        "aihubmix_configured": aihubmix_ok,
        "api_configured": api_ok,
        "ready": ready,
        "message": "；".join(msg_parts) if msg_parts else "就绪",
        "max_samples_per_job": settings.ORAL_GEN_MAX_SAMPLES_PER_JOB,
        "system_prompt": _system_prompt_preview(),
    }


def _system_prompt_preview() -> str:
    from app.utils.oral_practice import default_system_prompt

    return default_system_prompt()


def list_wav_paths(root: Optional[str] = None) -> list[str]:
    base = root or questionwav_dir()
    if not os.path.isdir(base):
        return []
    paths: list[str] = []
    for name in sorted(os.listdir(base)):
        if name.lower().endswith(".wav"):
            paths.append(os.path.join(base, name))
    return paths


def stem_from_path(path: str) -> str:
    return Path(path).stem


def sample_items(
    *,
    mode: Literal["all", "random"],
    count: int = 0,
    seed: Optional[int] = None,
    root: Optional[str] = None,
) -> list[dict[str, Any]]:
    paths = list_wav_paths(root)
    if not paths:
        raise FileNotFoundError(f"无可用 wav: {root or questionwav_dir()}")

    settings = get_settings()
    max_n = settings.ORAL_GEN_MAX_SAMPLES_PER_JOB

    if mode == "all":
        chosen = paths[:max_n]
    else:
        n = count if count > 0 else min(10, len(paths))
        n = min(n, len(paths), max_n)
        rng = random.Random(seed)
        chosen = rng.sample(paths, n)

    return [{"stem": stem_from_path(p), "path": p} for p in chosen]
