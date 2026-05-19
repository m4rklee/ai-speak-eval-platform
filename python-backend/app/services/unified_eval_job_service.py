"""Uni 统一语音评测任务：上传、Redis 状态、后台 run_directory_eval。"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from typing import Any, Optional

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.services.unified_eval_progress import JobProgressReporter, progress_detail_vo
from app.services.oral_eval.unified_eval_runner import (
    map_to_pronunciation,
    run_directory_eval,
    score_single_wav,
    validate_unified_eval_paths,
)

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "uni_eval:job:"
USER_JOBS_PREFIX = "uni_eval:user:"
JOB_TTL_SEC = 86400
MAX_FILES_PER_JOB = 200
MAX_FILE_BYTES = 50 * 1024 * 1024
USER_JOB_LIST_MAX = 20
AUDIO_CACHE_ROOT = "/tmp/uni_eval_audio"

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._\-]")


def _max_models_per_job() -> int:
    return get_settings().UNIFIED_EVAL_MAX_MODELS_PER_JOB


def _safe_model_dir_name(name: str) -> str:
    stem = _SAFE_NAME.sub("_", (name or "").strip())[:80] or "model"
    return stem


def _log_uni_eval_timing(**fields: Any) -> None:
    """Structured timing log; grep backend log with ``uni_eval_timing``."""
    payload: dict[str, Any] = {}
    for key, val in fields.items():
        if val is None:
            continue
        if isinstance(val, float):
            payload[key] = round(val, 2)
        else:
            payload[key] = val
    duration = payload.get("durationSec")
    files = payload.get("fileCount") or payload.get("totalFiles")
    if duration and files and int(files) > 0 and "secPerFile" not in payload:
        payload["secPerFile"] = round(float(duration) / int(files), 2)
    logger.info("uni_eval_timing %s", json.dumps(payload, ensure_ascii=False))


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def _user_jobs_key(user_id: int) -> str:
    return f"{USER_JOBS_PREFIX}{user_id}:jobs"


def _safe_wav_basename(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    if not base.lower().endswith(".wav"):
        base = f"{base}.wav" if base else "audio.wav"
    stem, ext = os.path.splitext(base)
    stem = _SAFE_NAME.sub("_", stem)[:120] or "audio"
    return f"{stem}{ext.lower()}"


def _audio_cache_dir(job_id: str) -> str:
    return os.path.join(AUDIO_CACHE_ROOT, job_id)


def _archive_job_audio(work_dir: str, job_id: str, *, multi_model: bool = False) -> Optional[str]:
    """评测完成后保留 wav 副本供回放（与任务 TTL 一致，目录在 /tmp）。"""
    if not os.path.isdir(work_dir):
        return None
    cache = _audio_cache_dir(job_id)
    os.makedirs(cache, exist_ok=True)
    copied = 0
    if multi_model:
        for model_dir in sorted(os.listdir(work_dir)):
            sub = os.path.join(work_dir, model_dir)
            if not os.path.isdir(sub):
                continue
            dest_sub = os.path.join(cache, model_dir)
            os.makedirs(dest_sub, exist_ok=True)
            for name in os.listdir(sub):
                if not name.lower().endswith(".wav"):
                    continue
                src = os.path.join(sub, name)
                if not os.path.isfile(src):
                    continue
                shutil.copy2(src, os.path.join(dest_sub, name))
                copied += 1
    else:
        for name in os.listdir(work_dir):
            if not name.lower().endswith(".wav"):
                continue
            src = os.path.join(work_dir, name)
            if not os.path.isfile(src):
                continue
            shutil.copy2(src, os.path.join(cache, name))
            copied += 1
    return cache if copied else None


def _unique_path(dest_dir: str, basename: str) -> str:
    path = os.path.join(dest_dir, basename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(basename)
    n = 1
    while True:
        candidate = os.path.join(dest_dir, f"{stem}_{n}{ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


async def _save_job(job_id: str, payload: dict[str, Any]) -> None:
    redis = get_redis()
    await redis.set(_job_key(job_id), json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SEC)


async def _load_job(job_id: str) -> Optional[dict[str, Any]]:
    redis = get_redis()
    raw = await redis.get(_job_key(job_id))
    if not raw:
        return None
    return json.loads(raw)


async def _push_user_job(user_id: int, job_id: str) -> None:
    redis = get_redis()
    key = _user_jobs_key(user_id)
    await redis.lrem(key, 0, job_id)
    await redis.lpush(key, job_id)
    await redis.ltrim(key, 0, USER_JOB_LIST_MAX - 1)
    await redis.expire(key, JOB_TTL_SEC)


def _per_file_to_row(entry: dict[str, Any]) -> dict[str, Any]:
    mapped = map_to_pronunciation(entry)
    multipa = entry.get("multipa") or {}
    transcripts = mapped.get("transcripts") or {}
    return {
        "wavname": entry.get("wavname", ""),
        "status": mapped.get("status", "error"),
        "accuracy": mapped.get("accuracy"),
        "fluency": mapped.get("fluency"),
        "naturalness": mapped.get("naturalness"),
        "apgMos": mapped.get("apg_mos"),
        "apgMosErrors": mapped.get("apg_mos_errors"),
        "transcriptS": transcripts.get("transcript_S", multipa.get("transcript_S", "")),
        "transcriptW": transcripts.get("transcript_W", multipa.get("transcript_W", "")),
        "reason": mapped.get("reason"),
        "raw": entry,
    }


def _summary_vo(summary_raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not summary_raw:
        return None
    return {
        "multipa": summary_raw.get("multipa"),
        "apgMosBvccMean": summary_raw.get("apg_mos_bvcc_mean"),
        "apgMosSomosMean": summary_raw.get("apg_mos_somos_mean"),
        "fileCount": summary_raw.get("file_count"),
    }


def _avg_num(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _compute_model_comparison(model_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: list[dict[str, Any]] = []
    for mr in model_results:
        per_file = mr.get("perFile") or []
        ok_rows = [r for r in per_file if r.get("status") == "ok"]
        acc = [float(r["accuracy"]) for r in ok_rows if isinstance(r.get("accuracy"), (int, float))]
        flu = [float(r["fluency"]) for r in ok_rows if isinstance(r.get("fluency"), (int, float))]
        nat = [float(r["naturalness"]) for r in ok_rows if isinstance(r.get("naturalness"), (int, float))]
        bvcc = []
        somos = []
        for r in ok_rows:
            apg = r.get("apgMos") or {}
            if isinstance(apg.get("bvcc"), (int, float)):
                bvcc.append(float(apg["bvcc"]))
            if isinstance(apg.get("somos"), (int, float)):
                somos.append(float(apg["somos"]))
        by_model.append(
            {
                "modelName": mr.get("modelName", ""),
                "fileCount": len(per_file),
                "accuracyMean": _avg_num(acc),
                "fluencyMean": _avg_num(flu),
                "naturalnessMean": _avg_num(nat),
                "apgMosBvccMean": _avg_num(bvcc),
                "apgMosSomosMean": _avg_num(somos),
            }
        )
    return {"byModel": by_model}


def _job_vo_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    job_type = payload.get("job_type") or "single"
    result = payload.get("result") or {}

    if job_type == "multi_model":
        models_raw = result.get("models") or payload.get("models") or []
        models_vo = []
        all_per_file: list[dict[str, Any]] = []
        for m in models_raw:
            per_file = m.get("perFile") or []
            for row in per_file:
                all_per_file.append({**row, "modelName": m.get("modelName", "")})
            models_vo.append(
                {
                    "modelName": m.get("modelName", ""),
                    "summary": _summary_vo(m.get("summary")),
                    "perFile": per_file,
                }
            )
        comparison = result.get("comparison") or payload.get("comparison")
        return {
            "jobId": payload.get("job_id", ""),
            "jobType": "multi_model",
            "status": payload.get("status", "pending"),
            "progress": payload.get("progress", 0),
            "totalFiles": payload.get("total_files", 0),
            "modelCount": payload.get("model_count", len(models_vo)),
            "error": payload.get("error"),
            "summary": None,
            "perFile": all_per_file if all_per_file else None,
            "models": models_vo if models_vo else None,
            "comparison": comparison,
            "result": result if result else None,
            "createdAt": payload.get("created_at"),
            "finishedAt": payload.get("finished_at"),
            "progressDetail": progress_detail_vo(payload.get("progress_detail")),
            "audioAvailable": bool(payload.get("audio_dir")),
        }

    summary_raw = result.get("summary")
    summary = _summary_vo(summary_raw)
    if payload.get("per_file_rows"):
        per_file = payload["per_file_rows"]
    elif result.get("per_file"):
        per_file = [_per_file_to_row(e) for e in result["per_file"]]
    else:
        per_file = None

    return {
        "jobId": payload.get("job_id", ""),
        "jobType": "single",
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalFiles": payload.get("total_files", 0),
        "modelCount": 0,
        "error": payload.get("error"),
        "summary": summary,
        "perFile": per_file,
        "models": None,
        "comparison": None,
        "result": result if result else None,
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(payload.get("progress_detail")),
        "audioAvailable": bool(payload.get("audio_dir")),
    }


class UnifiedEvalJobService:
    @staticmethod
    async def evaluate_single(file: UploadFile, user_id: int) -> dict[str, Any]:
        ok, reason = validate_unified_eval_paths()
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, reason)

        filename = file.filename or "sample.wav"
        if not filename.lower().endswith(".wav"):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "仅支持 .wav 文件")

        data = await file.read()
        if len(data) > MAX_FILE_BYTES:
            raise BusinessException(ErrorCode.PARAMS_ERROR, f"单文件不能超过 {MAX_FILE_BYTES // (1024 * 1024)}MB")
        if not data:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "文件为空")

        detail = await score_single_wav(
            data,
            model_name=f"uni_single_{user_id}",
        )
        transcripts = detail.get("transcripts") or {}
        return {
            "status": detail.get("status", "error"),
            "fileName": _safe_wav_basename(filename),
            "accuracy": detail.get("accuracy"),
            "fluency": detail.get("fluency"),
            "naturalness": detail.get("naturalness"),
            "apgMos": detail.get("apg_mos"),
            "apgMosErrors": detail.get("apg_mos_errors"),
            "transcripts": transcripts,
            "reason": detail.get("reason"),
            "raw": detail.get("raw"),
        }

    @staticmethod
    async def _read_upload_bounded(file: UploadFile) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise BusinessException(
                    ErrorCode.PARAMS_ERROR,
                    f"单文件不能超过 {MAX_FILE_BYTES // (1024 * 1024)}MB",
                )
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _materialize_wavs(
        dest_dir: str,
        files: list[UploadFile],
        archive: Optional[UploadFile],
    ) -> list[str]:
        written: list[str] = []

        if archive and archive.filename:
            if not archive.filename.lower().endswith(".zip"):
                raise BusinessException(ErrorCode.PARAMS_ERROR, "压缩包仅支持 .zip")
            data = await UnifiedEvalJobService._read_upload_bounded(archive)
            if not data:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "zip 文件为空")
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        name = info.filename.replace("\\", "/")
                        if ".." in name or name.startswith("/"):
                            continue
                        if not name.lower().endswith(".wav"):
                            continue
                        if len(written) >= MAX_FILES_PER_JOB:
                            break
                        basename = _safe_wav_basename(name)
                        out_path = _unique_path(dest_dir, basename)
                        with zf.open(info) as src, open(out_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        if os.path.getsize(out_path) > MAX_FILE_BYTES:
                            os.remove(out_path)
                            continue
                        written.append(os.path.basename(out_path))
            except zipfile.BadZipFile as e:
                raise BusinessException(ErrorCode.PARAMS_ERROR, f"无效的 zip 文件: {e}") from e

        for uf in files:
            if not uf.filename:
                continue
            if not uf.filename.lower().endswith(".wav"):
                raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型: {uf.filename}")
            if len(written) >= MAX_FILES_PER_JOB:
                break
            data = await UnifiedEvalJobService._read_upload_bounded(uf)
            if not data:
                continue
            basename = _safe_wav_basename(uf.filename)
            out_path = _unique_path(dest_dir, basename)
            with open(out_path, "wb") as f:
                f.write(data)
            written.append(os.path.basename(out_path))

        return written

    @staticmethod
    async def create_job(
        user_id: int,
        files: list[UploadFile],
        archive: Optional[UploadFile] = None,
    ) -> str:
        ok, reason = validate_unified_eval_paths()
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, reason)

        if not files and not archive:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请上传 wav 文件或 zip 压缩包")

        tmpdir = tempfile.mkdtemp(prefix="uni_eval_job_")
        try:
            written = await UnifiedEvalJobService._materialize_wavs(tmpdir, files, archive)
            if not written:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "未找到有效的 .wav 文件")
            if len(written) > MAX_FILES_PER_JOB:
                raise BusinessException(
                    ErrorCode.PARAMS_ERROR,
                    f"单任务最多 {MAX_FILES_PER_JOB} 个 wav 文件",
                )

            job_id = uuid.uuid4().hex
            now = datetime.now().isoformat(timespec="seconds")
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "job_type": "single",
                "status": "pending",
                "progress": 0,
                "total_files": len(written),
                "work_dir": tmpdir,
                "created_at": now,
                "finished_at": None,
                "error": None,
                "result": None,
            }
            await _save_job(job_id, payload)
            await _push_user_job(user_id, job_id)

            import asyncio

            asyncio.create_task(
                UnifiedEvalJobService._run_job(job_id, tmpdir, len(written))
            )
            return job_id
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    @staticmethod
    async def _run_job(job_id: str, work_dir: str, total_files: int) -> None:
        payload = await _load_job(job_id)
        if not payload:
            shutil.rmtree(work_dir, ignore_errors=True)
            return

        job_t0 = time.perf_counter()
        reporter = JobProgressReporter(job_id, total_files)
        await reporter.start()
        status = "failed"
        engine: Optional[str] = None
        error: Optional[str] = None

        try:
            merged = await run_directory_eval(
                work_dir,
                f"uni_{job_id}",
                job_id=job_id,
                reporter=reporter,
            )
            engine = merged.get("engine")
            per_file_rows = [_per_file_to_row(e) for e in merged.get("per_file", [])]
            await reporter.finish(success=True)
            payload = await _load_job(job_id) or payload
            payload["status"] = "completed"
            payload["progress"] = 100
            payload["result"] = merged
            payload["per_file_rows"] = per_file_rows
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            status = "completed"
        except Exception as e:
            logger.exception("Uni eval job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = 100
            payload["error"] = str(e)[:500]
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            error = str(e)[:500]
        finally:
            await reporter.stop()
            audio_dir = _archive_job_audio(work_dir, job_id)
            if audio_dir:
                payload["audio_dir"] = audio_dir
            shutil.rmtree(work_dir, ignore_errors=True)
            payload.pop("work_dir", None)
            await _save_job(job_id, payload)
            _log_uni_eval_timing(
                event="job_finished",
                jobId=job_id,
                jobType=payload.get("job_type") or "single",
                status=status,
                totalFiles=total_files,
                durationSec=time.perf_counter() - job_t0,
                engine=engine,
                error=error,
            )

    @staticmethod
    async def create_multi_model_job(user_id: int, form: Any) -> str:
        ok, reason = validate_unified_eval_paths()
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, reason)

        model_names = [str(n).strip() for n in form.getlist("modelNames") if str(n).strip()]
        if len(model_names) < 2:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "多模型对比至少需要 2 个模型")
        max_models = _max_models_per_job()
        if len(model_names) > max_models:
            raise BusinessException(ErrorCode.PARAMS_ERROR, f"单任务最多 {max_models} 个模型")

        seen: set[str] = set()
        unique_names: list[str] = []
        for name in model_names:
            key = name.lower()
            if key in seen:
                raise BusinessException(ErrorCode.PARAMS_ERROR, f"模型名重复: {name}")
            seen.add(key)
            unique_names.append(name)

        tmpdir = tempfile.mkdtemp(prefix="uni_eval_multi_")
        model_specs: list[dict[str, Any]] = []
        total_files = 0

        try:
            for idx, model_name in enumerate(unique_names):
                dir_name = _safe_model_dir_name(model_name)
                dest_dir = os.path.join(tmpdir, dir_name)
                os.makedirs(dest_dir, exist_ok=True)

                files_key = f"files_{idx}"
                archive_key = f"archive_{idx}"
                upload_files: list[UploadFile] = list(form.getlist(files_key))
                archive = form.get(archive_key)
                archive_file = archive if archive and getattr(archive, "filename", None) else None

                if not upload_files and not archive_file:
                    raise BusinessException(
                        ErrorCode.PARAMS_ERROR,
                        f"模型「{model_name}」未上传 wav 文件或 zip",
                    )

                written = await UnifiedEvalJobService._materialize_wavs(
                    dest_dir, upload_files, archive_file
                )
                if not written:
                    raise BusinessException(
                        ErrorCode.PARAMS_ERROR,
                        f"模型「{model_name}」未找到有效的 .wav 文件",
                    )
                total_files += len(written)
                model_specs.append(
                    {
                        "modelName": model_name,
                        "dirName": dir_name,
                        "fileCount": len(written),
                    }
                )

            job_id = uuid.uuid4().hex
            now = datetime.now().isoformat(timespec="seconds")
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "job_type": "multi_model",
                "model_count": len(model_specs),
                "model_specs": model_specs,
                "status": "pending",
                "progress": 0,
                "total_files": total_files,
                "work_dir": tmpdir,
                "created_at": now,
                "finished_at": None,
                "error": None,
                "result": None,
            }
            await _save_job(job_id, payload)
            await _push_user_job(user_id, job_id)

            import asyncio

            asyncio.create_task(
                UnifiedEvalJobService._run_multi_model_job(job_id, tmpdir, model_specs, total_files)
            )
            return job_id
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    @staticmethod
    async def _run_multi_model_job(
        job_id: str,
        work_dir: str,
        model_specs: list[dict[str, Any]],
        total_files: int,
    ) -> None:
        payload = await _load_job(job_id)
        if not payload:
            shutil.rmtree(work_dir, ignore_errors=True)
            return

        reporter = JobProgressReporter(job_id, max(1, total_files))
        await reporter.start()

        model_results: list[dict[str, Any]] = []
        files_done = 0
        job_t0 = time.perf_counter()
        status = "failed"
        error: Optional[str] = None

        try:
            for idx, spec in enumerate(model_specs):
                model_name = spec["modelName"]
                dir_name = spec["dirName"]
                subdir = os.path.join(work_dir, dir_name)
                n_files = spec["fileCount"]

                await reporter.begin_segment(n_files, files_done)
                await reporter.set_phase(
                    "parallel",
                    message=f"{model_name} · {idx + 1}/{len(model_specs)}",
                )

                merged = await run_directory_eval(
                    subdir,
                    model_name,
                    job_id=job_id,
                    reporter=reporter,
                )
                per_file_rows = [_per_file_to_row(e) for e in merged.get("per_file", [])]
                summary_raw = merged.get("summary") or {}
                model_results.append(
                    {
                        "modelName": model_name,
                        "summary": summary_raw,
                        "perFile": per_file_rows,
                    }
                )
                files_done += n_files
                await reporter.tick_file(
                    files_done,
                    message=f"已完成 {model_name} ({files_done}/{total_files})",
                )
                await reporter.sync_live_from_redis()

            comparison = _compute_model_comparison(model_results)
            await reporter.finish(success=True)
            payload = await _load_job(job_id) or payload
            payload["status"] = "completed"
            payload["progress"] = 100
            payload["result"] = {
                "models": model_results,
                "comparison": comparison,
            }
            payload["models"] = model_results
            payload["comparison"] = comparison
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            status = "completed"
        except Exception as e:
            logger.exception("Uni multi-model job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = 100
            payload["error"] = str(e)[:500]
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            error = str(e)[:500]
        finally:
            await reporter.stop()
            audio_dir = _archive_job_audio(work_dir, job_id, multi_model=True)
            if audio_dir:
                payload["audio_dir"] = audio_dir
            shutil.rmtree(work_dir, ignore_errors=True)
            payload.pop("work_dir", None)
            payload.pop("model_specs", None)
            await _save_job(job_id, payload)
            _log_uni_eval_timing(
                event="job_finished",
                jobId=job_id,
                jobType="multi_model",
                status=status,
                totalFiles=total_files,
                modelCount=len(model_specs),
                durationSec=time.perf_counter() - job_t0,
                error=error,
            )

    @staticmethod
    async def get_job(job_id: str, user_id: int) -> dict[str, Any]:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看该任务")
        return _job_vo_from_payload(payload)

    @staticmethod
    async def get_job_audio_path(
        job_id: str,
        user_id: int,
        filename: str,
        model_name: Optional[str] = None,
    ) -> str:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        safe = os.path.basename(filename.replace("\\", "/"))
        if not safe.lower().endswith(".wav"):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "仅支持 wav 文件")
        audio_dir = payload.get("audio_dir")
        if not audio_dir:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "该任务未保留音频（请重新评测）")

        job_type = payload.get("job_type") or "single"
        if job_type == "multi_model":
            if not model_name:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "多模型任务需指定 modelName")
            safe_model = _safe_model_dir_name(model_name)
            path = os.path.join(audio_dir, safe_model, safe)
            if not os.path.isfile(path):
                raise BusinessException(
                    ErrorCode.NOT_FOUND_ERROR,
                    f"音频不存在: {model_name}/{safe}",
                )
            return path

        path = os.path.join(audio_dir, safe)
        if not os.path.isfile(path):
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, f"音频不存在: {safe}")
        return path

    @staticmethod
    async def list_jobs(user_id: int) -> list[dict[str, Any]]:
        redis = get_redis()
        job_ids = await redis.lrange(_user_jobs_key(user_id), 0, USER_JOB_LIST_MAX - 1)
        out: list[dict[str, Any]] = []
        for jid in job_ids:
            payload = await _load_job(jid)
            if payload:
                out.append(_job_vo_from_payload(payload))
        return out
