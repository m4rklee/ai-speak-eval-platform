"""北极星 2201 内置题库加载与抽样。"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any, Literal, Optional

from app.core.config import get_settings


def _package_dir() -> Path:
    return Path(get_settings().listen_eval_package_dir)


def benchmark_path() -> Path:
    return _package_dir() / "data" / "benchmark.jsonl"


def audio_root() -> Path:
    return _package_dir() / "data" / "audio"


def load_all_items() -> list[dict[str, Any]]:
    path = benchmark_path()
    if not path.is_file():
        raise FileNotFoundError(f"题库不存在: {path}")

    items: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"无效 JSON 第 {line_number} 行: {exc}") from exc
    return items


def resolve_audio_path(item: dict[str, Any]) -> str:
    rel = item.get("audio_path") or ""
    if not rel:
        raise FileNotFoundError(f"题目 {item.get('id')} 无 audio_path")
    root = _package_dir()
    abs_path = (root / rel).resolve()
    if not abs_path.is_file():
        name = Path(rel).name
        alt = audio_root() / name
        if alt.is_file():
            return str(alt)
        raise FileNotFoundError(f"音频不存在: {abs_path}")
    return str(abs_path)


def sample_items(
    *,
    mode: Literal["all", "random"],
    count: int = 0,
    seed: Optional[int] = None,
) -> list[dict[str, Any]]:
    all_items = load_all_items()
    max_n = get_settings().LISTEN_EVAL_MAX_SAMPLES_PER_JOB
    if mode == "all":
        if len(all_items) > max_n:
            raise ValueError(f"全量题数 {len(all_items)} 超过上限 {max_n}")
        return all_items

    n = int(count)
    if n <= 0:
        raise ValueError("随机抽样数量须大于 0")
    if n > len(all_items):
        raise ValueError(f"抽样数 {n} 超过题库总量 {len(all_items)}")
    if n > max_n:
        raise ValueError(f"抽样数 {n} 超过单任务上限 {max_n}")

    rng = random.Random(seed)
    return rng.sample(all_items, n)


def health_check() -> dict[str, Any]:
    settings = get_settings()
    pkg = _package_dir()
    bench = benchmark_path()
    audio_dir = audio_root()

    bench_ok = bench.is_file()
    question_count = 0
    if bench_ok:
        try:
            question_count = len(load_all_items())
        except Exception:
            bench_ok = False

    audio_ok = audio_dir.is_dir()
    audio_file_count = 0
    if audio_ok:
        audio_file_count = sum(
            1
            for name in os.listdir(audio_dir)
            if name.lower().endswith((".wav", ".mp3"))
        )

    openrouter_ok = bool(settings.OPENROUTER_API_KEY.strip())
    aihubmix_ok = bool(settings.AIHUBMIX_API_KEY.strip())
    api_ok = openrouter_ok or aihubmix_ok

    messages: list[str] = []
    if not pkg.is_dir():
        messages.append(f"评测包目录不存在: {pkg}")
    if not bench_ok:
        messages.append(f"benchmark.jsonl 不可用: {bench}")
    elif question_count == 0:
        messages.append("题库为空")
    if not audio_ok:
        messages.append(f"音频目录不存在: {audio_dir}")

    return {
        "packageDirOk": pkg.is_dir(),
        "packageDir": str(pkg),
        "benchmarkOk": bench_ok,
        "benchmarkPath": str(bench),
        "questionCount": question_count,
        "audioDirOk": audio_ok,
        "audioDir": str(audio_dir),
        "audioFileCount": audio_file_count,
        "openrouterConfigured": openrouter_ok,
        "aihubmixConfigured": aihubmix_ok,
        "apiConfigured": api_ok,
        "ready": bool(
            pkg.is_dir() and bench_ok and question_count > 0 and audio_ok and api_ok
        ),
        "message": "；".join(messages) if messages else "ok",
        "maxSamplesPerJob": settings.LISTEN_EVAL_MAX_SAMPLES_PER_JOB,
    }
