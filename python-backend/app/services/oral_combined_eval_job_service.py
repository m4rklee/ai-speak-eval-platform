"""综合评测：wav + txt 成对，并行 Uni 语音 + 内容 Judge，单一任务 ID。"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.services.content_eval_job_service import ContentEvalJobService
from app.services.oral_eval import unified_eval_daemon_manager as daemon_mgr
from app.services.oral_eval.unified_eval_runner import (
    run_directory_eval,
    validate_unified_eval_paths,
)
from app.services.oral_combined_eval_progress import (
    JOB_TTL_SEC,
    OralCombinedProgressReporter,
    job_key,
    progress_detail_vo,
)
from app.services.unified_eval_job_service import _per_file_to_row
from app.utils.content_eval_questions import validate_question_dir

logger = logging.getLogger(__name__)

USER_JOBS_PREFIX = "oral_combined:user:"
USER_JOB_LIST_MAX = 20
MAX_FILES_PER_JOB = 200
MAX_WAV_BYTES = 50 * 1024 * 1024
MAX_TXT_BYTES = 2 * 1024 * 1024
AUDIO_CACHE_ROOT = "/tmp/oral_combined_audio"

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._\-]")


def _user_jobs_key(user_id: int) -> str:
    return f"{USER_JOBS_PREFIX}{user_id}:jobs"


def _question_dir():
    from app.services.content_eval_job_service import _question_dir as qdir

    return qdir()


def _max_files() -> int:
    return min(MAX_FILES_PER_JOB, get_settings().CONTENT_EVAL_MAX_FILES_PER_JOB)


def _safe_wav_basename(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    if not base.lower().endswith(".wav"):
        base = f"{base}.wav" if base else "audio.wav"
    stem, ext = os.path.splitext(base)
    stem = _SAFE_NAME.sub("_", stem)[:120] or "audio"
    return f"{stem}{ext.lower()}"


def _safe_txt_basename(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    if not base.lower().endswith(".txt"):
        base = f"{base}.txt" if base else "answer.txt"
    stem, ext = os.path.splitext(base)
    stem = _SAFE_NAME.sub("_", stem)[:120] or "answer"
    return f"{stem}{ext.lower()}"


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
    await redis.set(job_key(job_id), json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SEC)


async def _load_job(job_id: str) -> Optional[dict[str, Any]]:
    redis = get_redis()
    raw = await redis.get(job_key(job_id))
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


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            limit_mb = max_bytes // (1024 * 1024)
            raise BusinessException(ErrorCode.PARAMS_ERROR, f"单文件不能超过 {limit_mb}MB")
        chunks.append(chunk)
    return b"".join(chunks)


async def _materialize_pairs(
    dest_dir: str,
    files: list[UploadFile],
    archive: Optional[UploadFile],
) -> list[dict[str, str]]:
    wav_written: list[str] = []
    txt_written: list[str] = []
    max_files = _max_files()

    if archive and archive.filename:
        if not archive.filename.lower().endswith(".zip"):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "压缩包仅支持 .zip")
        data = await _read_upload_bounded(archive, MAX_WAV_BYTES)
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
                    lower = name.lower()
                    if lower.endswith(".wav"):
                        if len(wav_written) >= max_files:
                            continue
                        basename = _safe_wav_basename(name)
                        out_path = _unique_path(dest_dir, basename)
                        with zf.open(info) as src, open(out_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        if os.path.getsize(out_path) > MAX_WAV_BYTES:
                            os.remove(out_path)
                            continue
                        wav_written.append(os.path.basename(out_path))
                    elif lower.endswith(".txt"):
                        if len(txt_written) >= max_files:
                            continue
                        basename = _safe_txt_basename(name)
                        out_path = _unique_path(dest_dir, basename)
                        with zf.open(info) as src, open(out_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        if os.path.getsize(out_path) > MAX_TXT_BYTES:
                            os.remove(out_path)
                            continue
                        txt_written.append(os.path.basename(out_path))
        except zipfile.BadZipFile as e:
            raise BusinessException(ErrorCode.PARAMS_ERROR, f"无效的 zip 文件: {e}") from e

    for uf in files:
        if not uf.filename:
            continue
        lower = uf.filename.lower()
        if lower.endswith(".wav"):
            if len(wav_written) >= max_files:
                continue
            data = await _read_upload_bounded(uf, MAX_WAV_BYTES)
            if not data:
                continue
            basename = _safe_wav_basename(uf.filename)
            out_path = _unique_path(dest_dir, basename)
            with open(out_path, "wb") as f:
                f.write(data)
            wav_written.append(os.path.basename(out_path))
        elif lower.endswith(".txt"):
            if len(txt_written) >= max_files:
                continue
            data = await _read_upload_bounded(uf, MAX_TXT_BYTES)
            if not data:
                continue
            basename = _safe_txt_basename(uf.filename)
            out_path = _unique_path(dest_dir, basename)
            with open(out_path, "wb") as f:
                f.write(data)
            txt_written.append(os.path.basename(out_path))
        else:
            raise BusinessException(
                ErrorCode.PARAMS_ERROR,
                f"不支持的文件类型: {uf.filename}（仅 .wav 与 .txt）",
            )

    wav_by_stem = {Path(w).stem: w for w in wav_written}
    txt_by_stem = {Path(t).stem: t for t in txt_written}
    common = sorted(set(wav_by_stem) & set(txt_by_stem))
    only_wav = sorted(set(wav_by_stem) - set(txt_by_stem))
    only_txt = sorted(set(txt_by_stem) - set(wav_by_stem))

    if not common:
        parts = ["未找到 wav 与 txt 同名 stem 的成对文件"]
        if only_wav:
            parts.append(f"仅有 wav（{len(only_wav)} 个）: {', '.join(only_wav[:5])}")
            if len(only_wav) > 5:
                parts[-1] += "…"
        if only_txt:
            parts.append(f"仅有 txt（{len(only_txt)} 个）: {', '.join(only_txt[:5])}")
            if len(only_txt) > 5:
                parts[-1] += "…"
        raise BusinessException(ErrorCode.PARAMS_ERROR, "；".join(parts))

    if only_wav or only_txt:
        msg_parts = [f"已配对 {len(common)} 组"]
        if only_wav:
            msg_parts.append(f"缺少 txt: {', '.join(only_wav[:8])}")
            if len(only_wav) > 8:
                msg_parts[-1] += f" 等{len(only_wav)}个"
        if only_txt:
            msg_parts.append(f"缺少 wav: {', '.join(only_txt[:8])}")
            if len(only_txt) > 8:
                msg_parts[-1] += f" 等{len(only_txt)}个"
        raise BusinessException(ErrorCode.PARAMS_ERROR, "；".join(msg_parts))

    if len(common) > max_files:
        raise BusinessException(
            ErrorCode.PARAMS_ERROR,
            f"单任务最多 {max_files} 组成对样本",
        )

    return [
        {"stem": stem, "wavName": wav_by_stem[stem], "txtName": txt_by_stem[stem]}
        for stem in common
    ]


def _speech_side_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": row.get("status", "error"),
        "accuracy": row.get("accuracy"),
        "fluency": row.get("fluency"),
        "naturalness": row.get("naturalness"),
        "apgMos": row.get("apgMos"),
        "apgMosErrors": row.get("apgMosErrors"),
        "transcriptS": row.get("transcriptS", ""),
        "transcriptW": row.get("transcriptW", ""),
        "reason": row.get("reason"),
        "error": row.get("reason") if row.get("status") != "ok" else None,
    }


def _content_side_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": row.get("status", "error"),
        "questionId": row.get("questionId", ""),
        "question": row.get("question", ""),
        "grammarScore": row.get("grammarScore"),
        "themeFocusScore": row.get("themeFocusScore"),
        "answerClarityScore": row.get("answerClarityScore"),
        "compositeScore": row.get("compositeScore"),
        "reason": row.get("reason"),
        "error": row.get("error") or row.get("reason"),
    }


def _merge_row_status(speech: dict[str, Any], content: dict[str, Any]) -> str:
    s_ok = speech.get("status") == "ok"
    c_ok = content.get("status") == "ok"
    if s_ok and c_ok:
        return "ok"
    if s_ok or c_ok:
        return "partial"
    return "error"


def _compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if r.get("status") == "ok"]
    partial = [r for r in rows if r.get("status") == "partial"]

    def _avg(getter) -> Optional[float]:
        vals = []
        for r in ok + partial:
            v = getter(r)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return round(sum(vals) / len(vals), 2) if vals else None

    def _speech_get(r, key):
        sp = r.get("speech") or {}
        return sp.get(key)

    def _content_get(r, key):
        ct = r.get("content") or {}
        return ct.get(key)

    bvcc, somos = [], []
    for r in ok + partial:
        apg = (r.get("speech") or {}).get("apgMos") or {}
        if isinstance(apg.get("bvcc"), (int, float)):
            bvcc.append(float(apg["bvcc"]))
        if isinstance(apg.get("somos"), (int, float)):
            somos.append(float(apg["somos"]))

    def _avg_list(vals: list[float]) -> Optional[float]:
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "pairCount": len(rows),
        "okCount": len(ok),
        "partialCount": len(partial),
        "errorCount": len(rows) - len(ok) - len(partial),
        "accuracyMean": _avg(lambda r: _speech_get(r, "accuracy")),
        "fluencyMean": _avg(lambda r: _speech_get(r, "fluency")),
        "naturalnessMean": _avg(lambda r: _speech_get(r, "naturalness")),
        "apgMosBvccMean": _avg_list(bvcc),
        "apgMosSomosMean": _avg_list(somos),
        "grammarMean": _avg(lambda r: _content_get(r, "grammarScore")),
        "themeFocusMean": _avg(lambda r: _content_get(r, "themeFocusScore")),
        "answerClarityMean": _avg(lambda r: _content_get(r, "answerClarityScore")),
        "compositeMean": _avg(lambda r: _content_get(r, "compositeScore")),
    }


def _archive_combined_audio(work_dir: str, job_id: str) -> Optional[str]:
    if not os.path.isdir(work_dir):
        return None
    cache = os.path.join(AUDIO_CACHE_ROOT, job_id)
    os.makedirs(cache, exist_ok=True)
    copied = 0
    for name in os.listdir(work_dir):
        if not name.lower().endswith(".wav"):
            continue
        src = os.path.join(work_dir, name)
        if not os.path.isfile(src):
            continue
        shutil.copy2(src, os.path.join(cache, name))
        copied += 1
    return cache if copied else None


def _job_vo_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") or {}
    return {
        "jobId": payload.get("job_id", ""),
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalFiles": payload.get("total_files", 0),
        "error": payload.get("error"),
        "summary": payload.get("summary") or result.get("summary"),
        "perFile": payload.get("per_file_rows") or result.get("perFile"),
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(payload.get("progress_detail")),
        "audioAvailable": bool(payload.get("audio_dir")),
    }


class OralCombinedEvalJobService:
    @staticmethod
    async def health_async() -> dict[str, Any]:
        paths_ok, paths_msg = validate_unified_eval_paths()
        qdir = _question_dir()
        q_ok, q_msg, q_count = validate_question_dir(qdir)
        daemon_ok = await daemon_mgr.daemons_healthy()
        daemon_running = daemon_mgr.daemons_running()
        msg = paths_msg if paths_ok else paths_msg
        if paths_ok and not daemon_ok:
            msg = (
                f"{paths_msg}; " if paths_msg else ""
            ) + "评测 daemon 未就绪，请执行 bash scripts/eval-daemons.sh restart"
        return {
            "pathsOk": paths_ok,
            "pathsMessage": msg,
            "daemonRunning": daemon_running or daemon_ok,
            "daemonReady": daemon_ok,
            "questionDirOk": q_ok,
            "questionDirMessage": q_msg,
            "questionCount": q_count,
            "judgeModel": get_settings().ORAL_EVAL_JUDGE_MODEL,
            "maxFilesPerJob": _max_files(),
            "engine": "daemon",
        }

    @staticmethod
    async def create_job(
        user_id: int,
        files: list[UploadFile],
        archive: Optional[UploadFile] = None,
    ) -> str:
        h = await OralCombinedEvalJobService.health_async()
        if not h["pathsOk"]:
            raise BusinessException(ErrorCode.OPERATION_ERROR, h["pathsMessage"])
        if not h["daemonReady"]:
            raise BusinessException(ErrorCode.OPERATION_ERROR, h["pathsMessage"])
        if not h["questionDirOk"]:
            raise BusinessException(ErrorCode.OPERATION_ERROR, h["questionDirMessage"])

        if not files and not archive:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请上传 wav 与 txt 成对文件或 zip")

        tmpdir = tempfile.mkdtemp(prefix="oral_combined_job_")
        try:
            pairs = await _materialize_pairs(tmpdir, files, archive)
            job_id = uuid.uuid4().hex
            now = datetime.now().isoformat(timespec="seconds")
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "status": "pending",
                "progress": 0,
                "total_files": len(pairs),
                "pairs": pairs,
                "work_dir": tmpdir,
                "created_at": now,
                "finished_at": None,
                "error": None,
                "result": None,
            }
            await _save_job(job_id, payload)
            await _push_user_job(user_id, job_id)
            asyncio.create_task(OralCombinedEvalJobService._run_job(job_id, tmpdir, pairs))
            return job_id
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    @staticmethod
    async def _run_speech(
        job_id: str,
        work_dir: str,
        pair_count: int,
        reporter: OralCombinedProgressReporter,
    ) -> dict[str, Any]:
        try:
            merged = await run_directory_eval(
                work_dir,
                f"oral_combined_{job_id}",
                job_id=job_id,
            )
            await reporter.mark_speech_done()
            return merged
        except Exception as e:
            logger.exception("Combined job %s speech failed", job_id)
            await reporter.mark_speech_done()
            return {"per_file": [], "error": str(e)}

    @staticmethod
    async def _run_content(
        job_id: str,
        work_dir: str,
        pairs: list[dict[str, str]],
        reporter: OralCombinedProgressReporter,
    ) -> list[dict[str, Any]]:
        qdir = _question_dir()
        rows: list[dict[str, Any]] = []
        try:
            for idx, pair in enumerate(pairs, start=1):
                await reporter.update_content(idx - 1, pair["txtName"])
                row = await ContentEvalJobService._eval_one_file(
                    qdir, pair["txtName"], work_dir
                )
                row["stem"] = pair["stem"]
                rows.append(row)
                await reporter.update_content(idx, pair["txtName"])
            await reporter.mark_content_done()
            return rows
        except Exception as e:
            logger.exception("Combined job %s content failed", job_id)
            await reporter.mark_content_done()
            raise e

    @staticmethod
    async def _run_job(job_id: str, work_dir: str, pairs: list[dict[str, str]]) -> None:
        payload = await _load_job(job_id)
        if not payload:
            shutil.rmtree(work_dir, ignore_errors=True)
            return

        reporter = OralCombinedProgressReporter(job_id, len(pairs))
        await reporter.start()

        speech_merged: dict[str, Any] = {}
        content_rows: list[dict[str, Any]] = []
        run_error: Optional[str] = None

        try:
            speech_res, content_res = await asyncio.gather(
                OralCombinedEvalJobService._run_speech(
                    job_id, work_dir, len(pairs), reporter
                ),
                OralCombinedEvalJobService._run_content(job_id, work_dir, pairs, reporter),
                return_exceptions=True,
            )
            if isinstance(speech_res, BaseException):
                logger.exception("Combined job %s speech failed", job_id, exc_info=speech_res)
                speech_merged = {"per_file": [], "error": str(speech_res)[:500]}
                run_error = str(speech_res)[:500]
            else:
                speech_merged = speech_res
            if isinstance(content_res, BaseException):
                logger.exception("Combined job %s content failed", job_id, exc_info=content_res)
                content_rows = []
                run_error = run_error or str(content_res)[:500]
            else:
                content_rows = content_res
        except Exception as e:
            run_error = str(e)[:500]
            logger.exception("Combined job %s failed", job_id)

        speech_by_stem: dict[str, dict[str, Any]] = {}
        for entry in speech_merged.get("per_file") or []:
            row = _per_file_to_row(entry)
            stem = Path(row.get("wavname", "")).stem
            if stem:
                speech_by_stem[stem] = row

        content_by_stem: dict[str, dict[str, Any]] = {}
        for row in content_rows:
            stem = row.get("stem") or Path(row.get("fileName", "")).stem
            if stem:
                content_by_stem[stem] = row

        merged_rows: list[dict[str, Any]] = []
        for pair in pairs:
            stem = pair["stem"]
            sp_raw = speech_by_stem.get(stem, {"status": "error", "reason": "语音评测无结果"})
            ct_raw = content_by_stem.get(stem, {"status": "error", "error": "内容评测无结果"})
            speech = _speech_side_from_row(sp_raw)
            content = _content_side_from_row(ct_raw)
            merged_rows.append(
                {
                    "stem": stem,
                    "wavName": pair["wavName"],
                    "txtName": pair["txtName"],
                    "status": _merge_row_status(speech, content),
                    "speech": speech,
                    "content": content,
                }
            )

        summary = _compute_summary(merged_rows)
        success = not run_error and any(r.get("status") in ("ok", "partial") for r in merged_rows)

        payload = await _load_job(job_id) or payload
        if run_error and not merged_rows:
            payload["status"] = "failed"
            payload["error"] = run_error
        elif run_error:
            payload["status"] = "completed"
            payload["error"] = run_error
        else:
            payload["status"] = "completed" if success else "failed"
        payload["progress"] = 100
        payload["summary"] = summary
        payload["per_file_rows"] = merged_rows
        payload["result"] = {"summary": summary, "perFile": merged_rows}
        payload["finished_at"] = datetime.now().isoformat(timespec="seconds")

        await reporter.finish(success=payload["status"] == "completed")

        audio_dir = _archive_combined_audio(work_dir, job_id)
        if audio_dir:
            payload["audio_dir"] = audio_dir

        shutil.rmtree(work_dir, ignore_errors=True)
        payload.pop("work_dir", None)
        payload.pop("pairs", None)
        await _save_job(job_id, payload)

    @staticmethod
    async def get_job(job_id: str, user_id: int) -> dict[str, Any]:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看该任务")
        return _job_vo_from_payload(payload)

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

    @staticmethod
    async def get_job_audio_path(job_id: str, user_id: int, filename: str) -> str:
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
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "该任务未保留音频")
        path = os.path.join(audio_dir, safe)
        if not os.path.isfile(path):
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, f"音频不存在: {safe}")
        return path
