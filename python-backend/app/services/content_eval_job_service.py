"""内容评测任务：单条同步 + 批量 Redis 异步任务。"""
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
from app.services.content_eval_progress import (
    JOB_TTL_SEC,
    ContentEvalProgressReporter,
    progress_detail_vo,
)
from app.services.oral_eval.content_dimensions import evaluate_content_dimensions
from app.utils.content_eval_questions import (
    load_question,
    load_question_by_id,
    list_question_ids,
    validate_question_dir,
)

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "content_eval:job:"
USER_JOBS_PREFIX = "content_eval:user:"
USER_JOB_LIST_MAX = 20
MAX_FILE_BYTES = 2 * 1024 * 1024

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._\-]")


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def _user_jobs_key(user_id: int) -> str:
    return f"{USER_JOBS_PREFIX}{user_id}:jobs"


def _question_dir() -> Path:
    return Path(get_settings().content_eval_question_dir)


def _max_files() -> int:
    return get_settings().CONTENT_EVAL_MAX_FILES_PER_JOB


def _judge_model() -> str:
    return get_settings().ORAL_EVAL_JUDGE_MODEL


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


def _result_to_vo(
    *,
    file_name: str,
    question_id: str,
    question: str,
    answer: str = "",
    eval_result: dict[str, Any],
    status: str = "ok",
    error: Optional[str] = None,
) -> dict[str, Any]:
    dims = eval_result.get("dimensions") or {}
    grammar = dims.get("grammar") or {}
    theme = dims.get("themeFocus") or {}
    clarity = dims.get("answerClarity") or {}
    clarity_score = clarity.get("综合评分")
    if clarity_score is None:
        clarity_score = clarity.get("回复简洁清晰分数")
    return {
        "status": status if status != "ok" else eval_result.get("status", "ok"),
        "fileName": file_name,
        "questionId": question_id,
        "question": question,
        "answer": answer,
        "grammarScore": grammar.get("score"),
        "themeFocusScore": theme.get("主题聚焦拓展分数"),
        "answerClarityScore": clarity_score,
        "compositeScore": eval_result.get("composite") or eval_result.get("score"),
        "reason": eval_result.get("reason") or error,
        "dimensions": dims,
        "error": error,
    }


def _compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    def _avg(key: str) -> Optional[float]:
        vals = [r[key] for r in ok_rows if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "fileCount": len(rows),
        "okCount": len(ok_rows),
        "grammarMean": _avg("grammarScore"),
        "themeFocusMean": _avg("themeFocusScore"),
        "answerClarityMean": _avg("answerClarityScore"),
        "compositeMean": _avg("compositeScore"),
        "dimensions": [
            {"dimNameCn": "语法准确表达", "dimNameEn": "Grammar Accuracy", "score": _avg("grammarScore") or 0},
            {"dimNameCn": "主题聚焦拓展", "dimNameEn": "Theme Focus", "score": _avg("themeFocusScore") or 0},
            {"dimNameCn": "回复简洁清晰", "dimNameEn": "Answer Clarity", "score": _avg("answerClarityScore") or 0},
        ],
    }


def _job_vo_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") or {}
    summary = result.get("summary") or payload.get("summary")
    per_file = payload.get("per_file_rows") or result.get("perFile")
    return {
        "jobId": payload.get("job_id", ""),
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalFiles": payload.get("total_files", 0),
        "error": payload.get("error"),
        "summary": summary,
        "perFile": per_file,
        "result": result if result else None,
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(payload.get("progress_detail")),
    }


class ContentEvalJobService:
    @staticmethod
    def health() -> dict[str, Any]:
        qdir = _question_dir()
        ok, msg, count = validate_question_dir(qdir)
        return {
            "questionDirOk": ok,
            "questionDirMessage": msg,
            "questionCount": count,
            "questionDir": str(qdir),
            "judgeModel": _judge_model(),
            "maxFilesPerJob": _max_files(),
        }

    @staticmethod
    def list_questions(q: Optional[str] = None) -> dict[str, Any]:
        qdir = _question_dir()
        ids = list_question_ids(qdir)
        if q:
            needle = q.strip().lower()
            ids = [i for i in ids if needle in i.lower()]
        return {"ids": ids, "count": len(ids)}

    @staticmethod
    def get_question_text(question_id: str) -> dict[str, Any]:
        qdir = _question_dir()
        try:
            qid, text = load_question_by_id(qdir, question_id)
        except FileNotFoundError as e:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, str(e)) from e
        return {"questionId": qid, "question": text}

    @staticmethod
    async def evaluate_single(
        *,
        user_id: int,
        question_id: Optional[str],
        answer_text: Optional[str],
        file: Optional[UploadFile],
    ) -> dict[str, Any]:
        _ = user_id
        qdir = _question_dir()
        ok, msg, _ = validate_question_dir(qdir)
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, msg)

        file_name = "paste"
        answer = (answer_text or "").strip()
        qid = (question_id or "").strip()

        if file and file.filename:
            file_name = _safe_txt_basename(file.filename)
            data = await file.read()
            if len(data) > MAX_FILE_BYTES:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "单文件不能超过 2MB")
            answer = data.decode("utf-8", errors="replace").strip()
            if not answer:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "上传文件内容为空")
            stem = Path(file_name).stem
            try:
                matched_id, question = load_question(qdir, stem)
                qid = matched_id
            except FileNotFoundError:
                if not qid:
                    raise BusinessException(
                        ErrorCode.PARAMS_ERROR,
                        f"无法从文件名匹配内置题目: {file_name}，请选择题目 ID",
                    )
                _, question = load_question_by_id(qdir, qid)
        else:
            if not answer:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "请填写回答文本或上传 .txt 文件")
            if not qid:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "请选择题目 ID")
            _, question = load_question_by_id(qdir, qid)

        try:
            eval_result = await evaluate_content_dimensions(
                question=question,
                answer=answer,
                judge_model=_judge_model(),
            )
        except Exception as e:
            logger.exception("单条内容评测失败")
            raise BusinessException(
                ErrorCode.OPERATION_ERROR,
                f"内容评测 API 调用失败: {str(e)[:300]}",
            ) from e
        return _result_to_vo(
            file_name=file_name,
            question_id=qid,
            question=question,
            answer=answer,
            eval_result=eval_result,
        )

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
                raise BusinessException(ErrorCode.PARAMS_ERROR, "单文件不能超过 2MB")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _materialize_txts(
        dest_dir: str,
        files: list[UploadFile],
        archive: Optional[UploadFile],
    ) -> list[str]:
        written: list[str] = []
        max_files = _max_files()

        if archive and archive.filename:
            if not archive.filename.lower().endswith(".zip"):
                raise BusinessException(ErrorCode.PARAMS_ERROR, "压缩包仅支持 .zip")
            data = await ContentEvalJobService._read_upload_bounded(archive)
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
                        if not name.lower().endswith(".txt"):
                            continue
                        if len(written) >= max_files:
                            break
                        basename = _safe_txt_basename(name)
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
            if not uf.filename.lower().endswith(".txt"):
                raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型: {uf.filename}")
            if len(written) >= max_files:
                break
            data = await ContentEvalJobService._read_upload_bounded(uf)
            if not data:
                continue
            basename = _safe_txt_basename(uf.filename)
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
        qdir = _question_dir()
        ok, msg, _ = validate_question_dir(qdir)
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, msg)

        if not files and not archive:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请上传 .txt 文件或 zip 压缩包")

        tmpdir = tempfile.mkdtemp(prefix="content_eval_job_")
        try:
            written = await ContentEvalJobService._materialize_txts(tmpdir, files, archive)
            if not written:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "未找到有效的 .txt 文件")
            if len(written) > _max_files():
                raise BusinessException(
                    ErrorCode.PARAMS_ERROR,
                    f"单任务最多 {_max_files()} 个 txt 文件",
                )

            job_id = uuid.uuid4().hex
            now = datetime.now().isoformat(timespec="seconds")
            payload = {
                "job_id": job_id,
                "user_id": user_id,
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

            asyncio.create_task(
                ContentEvalJobService._run_job(job_id, tmpdir, written)
            )
            return job_id
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    @staticmethod
    async def _eval_one_file(qdir: Path, file_name: str, work_dir: str) -> dict[str, Any]:
        path = os.path.join(work_dir, file_name)
        answer = Path(path).read_text(encoding="utf-8", errors="replace").strip()
        if not answer:
            return _result_to_vo(
                file_name=file_name,
                question_id="",
                question="",
                answer="",
                eval_result={},
                status="error",
                error="文件内容为空",
            )
        stem = Path(file_name).stem
        try:
            qid, question = load_question(qdir, stem)
        except FileNotFoundError:
            return _result_to_vo(
                file_name=file_name,
                question_id="",
                question="",
                answer=answer,
                eval_result={},
                status="error",
                error=f"无匹配内置题目: {stem}",
            )
        try:
            eval_result = await evaluate_content_dimensions(
                question=question,
                answer=answer,
                judge_model=_judge_model(),
            )
            return _result_to_vo(
                file_name=file_name,
                question_id=qid,
                question=question,
                answer=answer,
                eval_result=eval_result,
            )
        except Exception as e:
            logger.exception("内容评测失败 %s", file_name)
            return _result_to_vo(
                file_name=file_name,
                question_id=qid,
                question=question,
                answer=answer,
                eval_result={},
                status="error",
                error=str(e)[:300],
            )

    @staticmethod
    async def _run_job(job_id: str, work_dir: str, file_names: list[str]) -> None:
        payload = await _load_job(job_id)
        if not payload:
            shutil.rmtree(work_dir, ignore_errors=True)
            return

        qdir = _question_dir()
        reporter = ContentEvalProgressReporter(job_id, len(file_names))
        rows: list[dict[str, Any]] = []

        try:
            for idx, name in enumerate(file_names, start=1):
                await reporter.update(idx - 1, message=name)
                row = await ContentEvalJobService._eval_one_file(qdir, name, work_dir)
                rows.append(row)
                await reporter.update(idx, message=name)

            summary = _compute_summary(rows)
            await reporter.finish(success=True)
            payload = await _load_job(job_id) or payload
            payload["status"] = "completed"
            payload["progress"] = 100
            payload["result"] = {"summary": summary, "perFile": rows}
            payload["per_file_rows"] = rows
            payload["summary"] = summary
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
        except Exception as e:
            logger.exception("Content eval job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = 100
            payload["error"] = str(e)[:500]
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
            payload.pop("work_dir", None)
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
