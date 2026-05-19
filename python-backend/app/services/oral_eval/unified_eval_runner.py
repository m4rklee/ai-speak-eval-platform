"""Run MultiPA + APG-MOS via 常驻 daemon。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime
from statistics import mean
from typing import Any, Optional, TYPE_CHECKING

import httpx

from app.core.config import get_settings
from app.models.batch_job_result import BatchJobResult
from app.services.oral_eval import unified_eval_daemon_manager as daemon_mgr
from app.services.unified_eval_progress import (
    clear_live_progress,
    init_live_progress,
    poll_live_progress,
)
from app.utils.audio_pcm import output_audio_json_to_wav_bytes

if TYPE_CHECKING:
    from app.services.unified_eval_progress import JobProgressReporter

logger = logging.getLogger(__name__)

_eval_semaphore = asyncio.Semaphore(1)

_DAEMON_UNAVAILABLE_MSG = (
    "MultiPA/APG-MOS 评测 daemon 未就绪，请执行: bash scripts/eval-daemons.sh restart"
)


async def _require_daemons_healthy() -> None:
    if not await daemon_mgr.daemons_healthy():
        raise RuntimeError(_DAEMON_UNAVAILABLE_MSG)


def _count_wavs_in_dir(directory: str) -> int:
    try:
        return sum(
            1
            for name in os.listdir(directory)
            if name.lower().endswith(".wav") and os.path.isfile(os.path.join(directory, name))
        )
    except OSError:
        return 0


def _log_uni_eval_timing(**fields: Any) -> None:
    payload: dict[str, Any] = {}
    for key, val in fields.items():
        if val is None:
            continue
        payload[key] = round(val, 2) if isinstance(val, float) else val
    duration = payload.get("durationSec")
    files = payload.get("fileCount")
    if duration and files and int(files) > 0 and "secPerFile" not in payload:
        payload["secPerFile"] = round(float(duration) / int(files), 2)
    logger.info("uni_eval_timing %s", json.dumps(payload, ensure_ascii=False))


def merge_multipa_apg(
    model_name: str,
    input_dir: str,
    multipa: dict,
    apg: dict,
) -> dict[str, Any]:
    """与 evaluate_speech_combined.merge_results 一致。"""
    per_file_map: dict[str, dict] = {}

    for item in multipa.get("per_file_results", []):
        wavname = item["wavname"]
        per_file_map[wavname] = {
            "wavname": wavname,
            "multipa": {
                "发音准确性": item.get("发音准确性"),
                "流利度": item.get("流利度"),
                "韵律": item.get("韵律"),
                "transcript_S": item.get("transcript_S", ""),
                "transcript_W": item.get("transcript_W", ""),
            },
            "apg_mos": {},
        }

    for label, model_data in apg.get("models", {}).items():
        for wavname, score in model_data.get("scores", {}).items():
            entry = per_file_map.setdefault(
                wavname,
                {"wavname": wavname, "multipa": None, "apg_mos": {}},
            )
            entry["apg_mos"][label] = score
        for wavname, err in model_data.get("errors", {}).items():
            entry = per_file_map.setdefault(
                wavname,
                {"wavname": wavname, "multipa": None, "apg_mos": {}},
            )
            entry.setdefault("apg_mos_errors", {})[label] = err

    per_file = sorted(per_file_map.values(), key=lambda x: x["wavname"])
    bvcc_scores = [
        e["apg_mos"]["bvcc"]
        for e in per_file
        if e.get("apg_mos", {}).get("bvcc") is not None
    ]
    somos_scores = [
        e["apg_mos"]["somos"]
        for e in per_file
        if e.get("apg_mos", {}).get("somos") is not None
    ]
    multipa_dims = {d["dim_name_cn"]: d["score"] for d in multipa.get("dimensions", [])}

    return {
        "model": model_name,
        "input_dir": os.path.abspath(input_dir),
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "engine": "daemon",
        "summary": {
            "multipa": multipa_dims,
            "apg_mos_bvcc_mean": round(mean(bvcc_scores), 4) if bvcc_scores else None,
            "apg_mos_somos_mean": round(mean(somos_scores), 4) if somos_scores else None,
            "file_count": len(per_file),
        },
        "per_file": per_file,
    }


async def _post_multipa_daemon(
    client: httpx.AsyncClient,
    settings: Any,
    payload: dict[str, str],
) -> dict[str, Any]:
    resp = await client.post(
        f"http://127.0.0.1:{settings.MULTIPA_DAEMON_PORT}/evaluate",
        json=payload,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or data.get("error"):
        raise RuntimeError(
            data.get("error") or f"MultiPA daemon HTTP {resp.status_code}"
        )
    return data


async def _post_apg_daemon(
    client: httpx.AsyncClient,
    settings: Any,
    input_dir: str,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    body: dict[str, str] = {"input_dir": input_dir}
    if job_id:
        body["job_id"] = job_id
    resp = await client.post(
        f"http://127.0.0.1:{settings.APG_DAEMON_PORT}/evaluate",
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data


async def _run_combined_via_daemon(
    input_dir: str,
    model_name: str,
    reporter: Optional["JobProgressReporter"] = None,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    settings = get_settings()
    timeout = float(settings.UNIFIED_EVAL_TIMEOUT_SEC)
    payload: dict[str, str] = {
        "input_dir": os.path.abspath(input_dir),
        "model_name": model_name,
    }
    if job_id:
        payload["job_id"] = job_id
    total = reporter._segment_files if reporter else 1
    parallel = settings.UNIFIED_EVAL_PARALLEL_DAEMON
    stop_poll = asyncio.Event()
    poll_task: Optional[asyncio.Task] = None

    if job_id:
        await init_live_progress(job_id, multipa_total=total, apg_total=total * 2)
        if reporter:
            poll_task = asyncio.create_task(poll_live_progress(job_id, reporter, stop_poll))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if parallel:
                if reporter:
                    await reporter.set_parallel_eval(total=total)

                async def run_multipa() -> dict[str, Any]:
                    try:
                        return await _post_multipa_daemon(client, settings, payload)
                    finally:
                        if reporter:
                            await reporter.mark_multipa_done()

                async def run_apg() -> dict[str, Any]:
                    try:
                        return await _post_apg_daemon(
                            client, settings, payload["input_dir"], job_id=job_id
                        )
                    finally:
                        if reporter:
                            await reporter.mark_apg_done()

                multipa, apg = await asyncio.gather(run_multipa(), run_apg())
            else:
                if reporter:
                    await reporter.set_phase(
                        "multipa",
                        current=0,
                        total=total,
                        message="MultiPA 发音评测中…",
                    )
                multipa = await _post_multipa_daemon(client, settings, payload)
                if reporter:
                    await reporter.mark_multipa_done()
                    await reporter.set_phase(
                        "apg",
                        current=0,
                        total=total,
                        message="APG-MOS 评分中…",
                    )
                apg = await _post_apg_daemon(
                    client, settings, payload["input_dir"], job_id=job_id
                )
                if reporter:
                    await reporter.mark_apg_done()

            if reporter:
                await reporter.set_phase("merging", current=0, total=1, message="合并结果…")

        merged = merge_multipa_apg(model_name, input_dir, multipa, apg)
        merged["parallel"] = parallel
        return merged
    finally:
        stop_poll.set()
        if poll_task:
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
        if reporter and job_id:
            await reporter.sync_live_from_redis()
        if job_id:
            await clear_live_progress(job_id)


def validate_unified_eval_paths() -> tuple[bool, str]:
    settings = get_settings()
    if not settings.UNIFIED_EVAL_ENABLED:
        return False, "UNIFIED_EVAL_ENABLED 未启用"
    multipa_py = settings.multipa_python_path
    if not os.path.isfile(multipa_py):
        return False, f"MultiPA Python 不存在: {multipa_py}"
    hubert = os.path.join(settings.MULTIPA_DIR, "fairseq_hubert", "hubert_base_ls960.pt")
    if not os.path.isfile(hubert):
        return False, f"HuBERT 权重不存在: {hubert}"
    for name in ("checkpoint_BVCC.pkl", "checkpoint_SOMOS.pkl"):
        ckpt = os.path.join(settings.APG_MOS_DIR, "checkpoints", name)
        if not os.path.isfile(ckpt):
            return False, f"APG-MOS checkpoint 不存在: {ckpt}"
    return True, ""


def map_to_pronunciation(
    entry: dict[str, Any],
    *,
    reference_text: str = "",
) -> dict[str, Any]:
    multipa = entry.get("multipa") or {}
    apg = entry.get("apg_mos") or {}
    apg_errors = entry.get("apg_mos_errors") or {}

    accuracy = multipa.get("发音准确性")
    fluency = multipa.get("流利度")
    naturalness = multipa.get("韵律")

    has_multipa = any(v is not None for v in (accuracy, fluency, naturalness))
    has_apg = bool(apg) or bool(apg_errors)

    if not has_multipa and not has_apg:
        return {
            "status": "error",
            "reason": "MultiPA 与 APG-MOS 均未返回有效分数",
            "raw": entry,
        }

    result: dict[str, Any] = {
        "status": "ok",
        "accuracy": float(accuracy) if accuracy is not None else 0.0,
        "fluency": float(fluency) if fluency is not None else 0.0,
        "naturalness": float(naturalness) if naturalness is not None else 0.0,
        "apg_mos": dict(apg) if apg else None,
        "apg_mos_errors": dict(apg_errors) if apg_errors else None,
        "transcripts": {
            "transcript_S": multipa.get("transcript_S", ""),
            "transcript_W": multipa.get("transcript_W", ""),
        },
        "reference_text": reference_text,
        "raw": entry,
    }
    if not has_multipa:
        result["multipa_missing"] = True
    return result


def build_wav_dir(
    rows: list[BatchJobResult],
) -> tuple[Optional[str], dict[str, str], dict[str, str]]:
    """
    Write {result.id}.wav into a temp directory.

    Returns:
        tmpdir (or None if no wavs), wav_basename -> result_id, skipped result_id -> reason
    """
    tmpdir = tempfile.mkdtemp(prefix="unified_eval_job_")
    id_by_wav: dict[str, str] = {}
    skipped: dict[str, str] = {}
    written = 0

    for row in rows:
        rid = str(row.id)
        if not row.output_audio:
            skipped[rid] = "无输出音频"
            continue
        try:
            wav_bytes, _ = output_audio_json_to_wav_bytes(row.output_audio)
            wav_name = f"{rid}.wav"
            path = os.path.join(tmpdir, wav_name)
            with open(path, "wb") as f:
                f.write(wav_bytes)
            id_by_wav[wav_name] = rid
            written += 1
        except Exception as e:
            skipped[rid] = str(e)[:500]

    if written == 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, {}, skipped

    return tmpdir, id_by_wav, skipped


async def run_directory_eval(
    input_dir: str,
    model_name: str,
    *,
    job_id: Optional[str] = None,
    reporter: Optional["JobProgressReporter"] = None,
) -> dict[str, Any]:
    eval_t0 = time.perf_counter()
    file_count = _count_wavs_in_dir(input_dir)
    status = "failed"

    async with _eval_semaphore:
        await _require_daemons_healthy()
        if reporter:
            reporter.engine = "daemon"

        try:
            logger.info("Unified eval via daemon: %s", input_dir)
            merged = await _run_combined_via_daemon(
                input_dir, model_name, reporter, job_id=job_id
            )
            status = "completed"
            return merged
        finally:
            _log_uni_eval_timing(
                event="directory_eval_finished",
                jobId=job_id,
                modelName=model_name,
                fileCount=file_count,
                engine="daemon",
                status=status,
                durationSec=time.perf_counter() - eval_t0,
            )


async def score_batch_rows(
    rows: list[BatchJobResult],
    *,
    job_id: str,
    pron_cfg: Optional[dict[str, Any]] = None,
) -> dict[str, dict[str, Any]]:
    """
    Batch pronunciation for job results.

    Returns result_id -> pronunciation detail dict.
    """
    ok, reason = validate_unified_eval_paths()
    if not ok:
        return {str(r.id): {"status": "skipped", "reason": reason} for r in rows}

    pron_cfg = pron_cfg or {}
    if pron_cfg.get("enabled") is False:
        return {str(r.id): {"status": "skipped", "reason": "发音评测已禁用"} for r in rows}

    provider = (pron_cfg.get("provider") or "").strip().lower()
    base_url = (pron_cfg.get("baseUrl") or "").strip()
    if provider == "http" or (base_url and provider != "unified"):
        return {}

    tmpdir, id_by_wav, skipped = build_wav_dir(rows)
    out: dict[str, dict[str, Any]] = {
        rid: {"status": "skipped", "reason": msg} for rid, msg in skipped.items()
    }

    if not tmpdir:
        return out

    ref_from = pron_cfg.get("refTextFrom", "output_content")
    ref_by_id: dict[str, str] = {}
    for row in rows:
        rid = str(row.id)
        if ref_from == "output_content":
            ref_by_id[rid] = row.output_content or row.expected_answer or row.prompt or ""
        else:
            ref_by_id[rid] = row.expected_answer or row.output_content or row.prompt or ""

    try:
        merged = await run_directory_eval(
            tmpdir,
            f"batch_{job_id}",
            job_id=job_id,
        )
        per_file = {item["wavname"]: item for item in merged.get("per_file", [])}

        for wav_name, result_id in id_by_wav.items():
            entry = per_file.get(wav_name)
            if not entry:
                out[result_id] = {
                    "status": "error",
                    "reason": f"统一评测结果中未找到 {wav_name}",
                }
                continue
            out[result_id] = map_to_pronunciation(
                entry,
                reference_text=ref_by_id.get(result_id, ""),
            )
    except Exception as e:
        logger.exception("Unified batch eval failed for job %s", job_id)
        for wav_name, result_id in id_by_wav.items():
            if result_id not in out or out[result_id].get("status") != "skipped":
                out[result_id] = {
                    "status": "error",
                    "reason": str(e)[:500],
                }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return out


async def score_single_wav(
    wav_bytes: bytes,
    *,
    model_name: str = "inline_eval",
    reference_text: str = "",
) -> dict[str, Any]:
    """Score one wav file via unified eval."""
    ok, reason = validate_unified_eval_paths()
    if not ok:
        return {"status": "skipped", "reason": reason}

    tmpdir = tempfile.mkdtemp(prefix="unified_eval_single_")
    wav_path = os.path.join(tmpdir, "sample.wav")
    try:
        with open(wav_path, "wb") as f:
            f.write(wav_bytes)
        merged = await run_directory_eval(tmpdir, model_name)
        per_file = merged.get("per_file") or []
        if not per_file:
            return {"status": "error", "reason": "统一评测无 per_file 结果"}
        return map_to_pronunciation(per_file[0], reference_text=reference_text)
    except Exception as e:
        logger.exception("Unified single eval failed")
        return {"status": "error", "reason": str(e)[:500]}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
