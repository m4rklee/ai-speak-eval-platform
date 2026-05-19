#!/usr/bin/env python3
"""
将北极星旧数据集 questiontext + gpt-audio transcripts 合并为平台「批量文本评分」可导入的 JSON。

用法:
  python scripts/build_polar_import_json.py \\
    --manifest "/path/to/answerwav_openai_gpt-audio/manifest.jsonl" \\
    --question-dir "/path/to/questiontext" \\
    -o ./polar_gpt_audio_import.json

也可只指定数据集根目录（含 manifest 与 questiontext 的公共父路径）:
  python scripts/build_polar_import_json.py \\
    --dataset-root "/path/to/旧数据集" \\
    --model-dir answerwav_openai_gpt-audio \\
    -o ./polar_gpt_audio_import.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Optional


def resolve_question_file(question_dir: Path, transcript_stem: str) -> Optional[Path]:
    """transcripts 文件名可能与 questiontext 不完全一致（如 00174_环境安静_女 → 00174.txt）"""
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


def load_from_manifest(
    manifest_path: Path,
    question_dir: Path,
    *,
    only_ok: bool = True,
) -> list[dict]:
    items: list[dict] = []
    skipped = 0
    with manifest_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if only_ok and row.get("status") != "ok":
                skipped += 1
                continue
            transcript_path = Path(row.get("transcript_file") or "")
            if not transcript_path.is_file():
                # fallback: transcript inline in manifest
                transcript_text = (row.get("transcript") or "").strip()
                stem = Path(row.get("output", "item")).stem
            else:
                transcript_text = transcript_path.read_text(encoding="utf-8").strip()
                stem = transcript_path.stem

            qfile = resolve_question_file(question_dir, stem)
            if not qfile:
                print(f"WARN line {line_no}: 无匹配题目 stem={stem}")
                skipped += 1
                continue
            prompt = qfile.read_text(encoding="utf-8").strip()
            if not transcript_text:
                print(f"WARN line {line_no}: 空转录 stem={stem}")
                skipped += 1
                continue

            items.append(
                {
                    "id": stem,
                    "prompt": prompt,
                    "expectedAnswer": "-",
                    "modelOutput": transcript_text,
                    "category": "oral_practice",
                    "meta": {
                        "questionFile": str(qfile.name),
                        "transcriptFile": str(transcript_path.name) if transcript_path.is_file() else None,
                        "outputWav": row.get("output"),
                    },
                }
            )
    if skipped:
        print(f"跳过 {skipped} 条")
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="生成平台批量文本评分导入 JSON")
    parser.add_argument("--manifest", type=Path, help="manifest.jsonl 路径")
    parser.add_argument("--question-dir", type=Path, help="questiontext 目录")
    parser.add_argument("--transcripts-dir", type=Path, help="可选：仅扫描 transcripts 目录（无 manifest 时）")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        help="旧数据集根目录，与 --model-dir 联用",
    )
    parser.add_argument(
        "--model-dir",
        default="answerwav_openai_gpt-audio",
        help="数据集根下模型输出目录名（默认 answerwav_openai_gpt-audio）",
    )
    parser.add_argument("-o", "--output", type=Path, required=True, help="输出 JSON 文件")
    parser.add_argument(
        "--platform-format",
        action="store_true",
        help="仅输出 prompt/expectedAnswer/modelOutput（去掉 id/meta，直接用于前端导入）",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        metavar="N",
        help="随机抽取 N 条（0 表示全量）",
    )
    parser.add_argument("--seed", type=int, default=None, help="随机种子（可复现抽样）")
    args = parser.parse_args()

    if args.dataset_root:
        root = args.dataset_root.resolve()
        manifest = root / args.model_dir / "manifest.jsonl"
        question_dir = root / "questiontext"
    else:
        if not args.manifest or not args.question_dir:
            parser.error("请提供 --manifest 与 --question-dir，或 --dataset-root")
        manifest = args.manifest.resolve()
        question_dir = args.question_dir.resolve()

    if not manifest.is_file():
        raise SystemExit(f"manifest 不存在: {manifest}")
    if not question_dir.is_dir():
        raise SystemExit(f"questiontext 目录不存在: {question_dir}")

    items = load_from_manifest(manifest, question_dir)
    items.sort(key=lambda x: x["id"])
    total = len(items)

    if args.seed is not None:
        random.seed(args.seed)
    if args.sample and args.sample > 0 and args.sample < total:
        items = random.sample(items, args.sample)
        print(f"随机抽样 {len(items)} / {total} 条（seed={args.seed}）")
    elif args.sample and args.sample > 0:
        print(f"N={args.sample} 不小于总数，输出全量 {total} 条")

    if args.platform_format:
        out = [
            {
                "prompt": it["prompt"],
                "expectedAnswer": it["expectedAnswer"],
                "modelOutput": it["modelOutput"],
            }
            for it in items
        ]
    else:
        out = items

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {len(out)} 条 → {args.output}")


if __name__ == "__main__":
    main()
