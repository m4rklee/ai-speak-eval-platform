"""内容评测内置 question 题库解析与匹配。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def resolve_question_file(question_dir: Path, transcript_stem: str) -> Optional[Path]:
    """answer 文件名 stem 匹配 questiontext（如 00174_环境安静_女 → 00174.txt）。"""
    direct = question_dir / f"{transcript_stem}.txt"
    if direct.is_file():
        return direct
    m = re.match(r"^(\d+)", transcript_stem)
    if not m:
        return None
    num = int(m.group(1))
    for name in (f"{num:05d}.txt", f"{num}.txt", f"{m.group(1)}.txt"):
        cand = question_dir / name
        if cand.is_file():
            return cand
    return None


def question_id_from_path(qfile: Path) -> str:
    return qfile.stem


def load_question(question_dir: Path, stem: str) -> tuple[str, str]:
    """返回 (question_id, question_text)。"""
    qfile = resolve_question_file(question_dir, stem)
    if not qfile:
        raise FileNotFoundError(f"无匹配内置题目: stem={stem}")
    return question_id_from_path(qfile), qfile.read_text(encoding="utf-8").strip()


def load_question_by_id(question_dir: Path, question_id: str) -> tuple[str, str]:
    """按题目 ID（如 00001 或 1）加载 question。"""
    stem = question_id.strip()
    if stem.isdigit():
        num = int(stem)
        for name in (f"{num:05d}.txt", f"{num}.txt", f"{stem}.txt"):
            cand = question_dir / name
            if cand.is_file():
                return question_id_from_path(cand), cand.read_text(encoding="utf-8").strip()
    qfile = question_dir / f"{stem}.txt"
    if qfile.is_file():
        return question_id_from_path(qfile), qfile.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"无匹配内置题目: id={question_id}")


def list_question_ids(question_dir: Path) -> list[str]:
    ids: list[str] = []
    if not question_dir.is_dir():
        return ids
    for p in sorted(question_dir.glob("*.txt")):
        ids.append(p.stem)
    return ids


def validate_question_dir(path: Path) -> tuple[bool, str, int]:
    if not path.is_dir():
        return False, f"题库目录不存在: {path}", 0
    count = len(list(path.glob("*.txt")))
    if count == 0:
        return False, f"题库目录为空: {path}", 0
    return True, "ok", count
