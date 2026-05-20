"""内容评测任务：单条同步 + 批量 Redis 异步任务。"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import shutil
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
from app.services.eval_job_meta import (
    apply_create_meta,
    meta_vo,
    update_display_name as apply_display_name,
)
from app.services.eval_rounds import aggregate_content_eval_results
from app.services.job_progress import (
    api_error_vo,
    append_warning_to_detail,
    record_row_error,
)
from app.services.job_control import (
    assert_can_pause,
    assert_can_rerun,
    check_pause_requested,
    control_meta_vo,
    eval_job_input_dir,
    prepare_rerun_payload,
    request_pause,
    save_input_snapshot,
)
from app.services.job_resume import assert_can_resume, resume_meta_vo, wrap_task
from app.services.oral_eval.content_dimensions import evaluate_content_dimensions
from app.services.token_aggregate import add_tokens_with_cost, ensure_estimated_cost, token_summary_vo
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
    judge_model: Optional[str] = None,
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
        "inputTokens": eval_result.get("inputTokens"),
        "outputTokens": eval_result.get("outputTokens"),
        "judgeModel": judge_model or _judge_model(),
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


def _max_models_per_job() -> int:
    return get_settings().UNIFIED_EVAL_MAX_MODELS_PER_JOB


def _safe_model_dir_name(name: str) -> str:
    stem = _SAFE_NAME.sub("_", (name or "").strip())[:80] or "model"
    return stem


def _avg_num(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _compute_content_model_comparison(model_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: list[dict[str, Any]] = []
    for mr in model_results:
        per_file = mr.get("perFile") or []
        ok_rows = [r for r in per_file if r.get("status") == "ok"]

        def _mean(key: str) -> Optional[float]:
            vals = [float(r[key]) for r in ok_rows if isinstance(r.get(key), (int, float))]
            return _avg_num(vals)

        by_model.append(
            {
                "modelName": mr.get("modelName", ""),
                "fileCount": len(per_file),
                "grammarMean": _mean("grammarScore"),
                "themeFocusMean": _mean("themeFocusScore"),
                "answerClarityMean": _mean("answerClarityScore"),
                "compositeMean": _mean("compositeScore"),
            }
        )
    return {"byModel": by_model}


def _job_vo_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    job_type = payload.get("job_type") or "single"
    result = payload.get("result") or {}

    if job_type == "multi_model":
        models_raw = (
            result.get("models")
            or payload.get("models")
            or payload.get("partial_model_results")
            or []
        )
        models_vo: list[dict[str, Any]] = []
        all_per_file: list[dict[str, Any]] = []
        for m in models_raw:
            per_file = m.get("perFile") or []
            for row in per_file:
                all_per_file.append({**row, "modelName": m.get("modelName", "")})
            models_vo.append(
                {
                    "modelName": m.get("modelName", ""),
                    "summary": m.get("summary"),
                    "perFile": per_file,
                }
            )
        comparison = result.get("comparison") or payload.get("comparison")
        meta = resume_meta_vo(payload)
        detail = append_warning_to_detail(payload.get("progress_detail"), payload)
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
            "progressDetail": progress_detail_vo(detail),
            **meta_vo(payload),
            **api_error_vo(payload),
            **token_summary_vo(payload),
            **meta,
            **control_meta_vo(payload, JOB_KEY_PREFIX, payload.get("job_id", "")),
        }

    summary = result.get("summary") or payload.get("summary")
    per_file = (
        payload.get("partial_per_file_rows")
        or payload.get("per_file_rows")
        or result.get("perFile")
    )
    meta = resume_meta_vo(payload)
    detail = append_warning_to_detail(payload.get("progress_detail"), payload)
    return {
        "jobId": payload.get("job_id", ""),
        "jobType": job_type if job_type != "single" else None,
        "status": payload.get("status", "pending"),
        "progress": payload.get("progress", 0),
        "totalFiles": payload.get("total_files", 0),
        "error": payload.get("error"),
        "summary": summary,
        "perFile": per_file,
        "result": result if result else None,
        "createdAt": payload.get("created_at"),
        "finishedAt": payload.get("finished_at"),
        "progressDetail": progress_detail_vo(detail),
        **meta_vo(payload),
        **api_error_vo(payload),
        **token_summary_vo(payload),
        **meta,
        **control_meta_vo(payload, JOB_KEY_PREFIX, payload.get("job_id", "")),
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
        *,
        display_name: Optional[str] = None,
        eval_rounds: Optional[int] = None,
        judge_model: Optional[str] = None,
    ) -> str:
        qdir = _question_dir()
        ok, msg, _ = validate_question_dir(qdir)
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, msg)

        if not files and not archive:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请上传 .txt 文件或 zip 压缩包")

        job_id = uuid.uuid4().hex
        tmpdir = eval_job_input_dir(job_id)
        try:
            os.makedirs(tmpdir, exist_ok=True)
            written = await ContentEvalJobService._materialize_txts(tmpdir, files, archive)
            if not written:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "未找到有效的 .txt 文件")
            if len(written) > _max_files():
                raise BusinessException(
                    ErrorCode.PARAMS_ERROR,
                    f"单任务最多 {_max_files()} 个 txt 文件",
                )

            now = datetime.now().isoformat(timespec="seconds")
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "job_type": "single",
                "status": "pending",
                "progress": 0,
                "total_files": len(written),
                "work_dir": tmpdir,
                "file_names": written,
                "partial_per_file_rows": [],
                "completed_count": 0,
                "created_at": now,
                "finished_at": None,
                "error": None,
                "result": None,
                "api_error_count": 0,
            }
            apply_create_meta(
                payload,
                job_type="content",
                display_name=display_name,
                eval_rounds=eval_rounds,
                judge_model=judge_model,
            )
            save_input_snapshot(
                payload,
                work_dir=tmpdir,
                file_names=written,
                job_type="single",
                total_files=len(written),
                judge_model=payload.get("judge_model"),
                eval_rounds=payload.get("eval_rounds"),
                display_name=payload.get("display_name"),
            )
            await _save_job(job_id, payload)
            await _push_user_job(user_id, job_id)

            wrap_task(
                JOB_KEY_PREFIX,
                job_id,
                ContentEvalJobService._run_job(job_id),
            )
            return job_id
        except Exception:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    @staticmethod
    async def _eval_one_file(
        qdir: Path,
        file_name: str,
        work_dir: str,
        *,
        judge_model: Optional[str] = None,
        eval_rounds: int = 1,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
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
        jm = (judge_model or _judge_model()).strip()
        round_results: list[dict[str, Any]] = []
        try:
            for _ in range(max(1, eval_rounds)):
                eval_result = await evaluate_content_dimensions(
                    question=question,
                    answer=answer,
                    judge_model=jm,
                )
                round_results.append(eval_result)
                if payload is not None:
                    await add_tokens_with_cost(
                        payload,
                        int(eval_result.get("inputTokens") or 0),
                        int(eval_result.get("outputTokens") or 0),
                    )
            if len(round_results) > 1:
                eval_result = aggregate_content_eval_results(round_results)
            else:
                eval_result = round_results[0] if round_results else {}
            vo = _result_to_vo(
                file_name=file_name,
                question_id=qid,
                question=question,
                answer=answer,
                eval_result=eval_result,
                judge_model=jm,
            )
            if payload is not None:
                record_row_error(payload, vo)
            return vo
        except Exception as e:
            logger.exception("内容评测失败 %s", file_name)
            vo = _result_to_vo(
                file_name=file_name,
                question_id=qid,
                question=question,
                answer=answer,
                eval_result={},
                status="error",
                error=str(e)[:300],
                judge_model=jm,
            )
            if payload is not None:
                record_row_error(payload, vo)
            return vo

    @staticmethod
    async def resume_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_resume(payload, job_id, JOB_KEY_PREFIX)
        work_dir = payload.get("work_dir")
        if not work_dir or not os.path.isdir(work_dir):
            raise BusinessException(ErrorCode.OPERATION_ERROR, "工作目录不可用，无法续跑")
        payload["status"] = "running"
        payload["error"] = None
        await _save_job(job_id, payload)
        if payload.get("job_type") == "multi_model":
            wrap_task(
                JOB_KEY_PREFIX,
                job_id,
                ContentEvalJobService._run_multi_model_job(job_id),
            )
        else:
            wrap_task(JOB_KEY_PREFIX, job_id, ContentEvalJobService._run_job(job_id))

    @staticmethod
    async def pause_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_pause(payload, job_id, JOB_KEY_PREFIX)
        request_pause(payload)
        await _save_job(job_id, payload)

    @staticmethod
    async def rerun_job(user_id: int, job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        assert_can_rerun(payload, job_id, JOB_KEY_PREFIX)
        prepare_rerun_payload(payload)
        await _save_job(job_id, payload)
        if payload.get("job_type") == "multi_model":
            wrap_task(
                JOB_KEY_PREFIX,
                job_id,
                ContentEvalJobService._run_multi_model_job(job_id),
            )
        else:
            wrap_task(JOB_KEY_PREFIX, job_id, ContentEvalJobService._run_job(job_id))

    @staticmethod
    async def _run_job(job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            return

        work_dir = payload.get("work_dir")
        file_names: list[str] = payload.get("file_names") or []
        if not work_dir or not file_names:
            payload["status"] = "failed"
            payload["error"] = "任务输入数据已丢失"
            await _save_job(job_id, payload)
            return

        qdir = _question_dir()
        eval_rounds = int(payload.get("eval_rounds") or 1)
        judge_model = payload.get("judge_model")
        rows: list[dict[str, Any]] = list(payload.get("partial_per_file_rows") or [])
        start_idx = len(rows)
        total_units = len(file_names) * eval_rounds
        units_done = start_idx * eval_rounds
        reporter = ContentEvalProgressReporter(job_id, total_units, offset=units_done)

        if start_idx > 0:
            await reporter.update(units_done, message="续跑中…")

        try:
            for idx in range(start_idx, len(file_names)):
                name = file_names[idx]
                await reporter.update(idx * eval_rounds, message=name)
                row = await ContentEvalJobService._eval_one_file(
                    qdir,
                    name,
                    work_dir,
                    judge_model=judge_model,
                    eval_rounds=eval_rounds,
                    payload=payload,
                )
                rows.append(row)
                payload = await _load_job(job_id) or payload
                payload["partial_per_file_rows"] = rows
                payload["completed_count"] = len(rows)
                await _save_job(job_id, payload)
                await reporter.update((idx + 1) * eval_rounds, message=name)
                if await check_pause_requested(_load_job, job_id, payload):
                    return

            summary = _compute_summary(rows)
            await reporter.finish(success=True)
            payload = await _load_job(job_id) or payload
            payload["status"] = "completed"
            payload["progress"] = 100
            payload["result"] = {"summary": summary, "perFile": rows}
            payload["per_file_rows"] = rows
            payload["summary"] = summary
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
            payload.pop("partial_per_file_rows", None)
            payload.pop("completed_count", None)
            payload.pop("file_names", None)
        except Exception as e:
            logger.exception("Content eval job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = int(min(99, (len(rows) / max(1, len(file_names))) * 100))
            payload["error"] = str(e)[:500]
            payload["partial_per_file_rows"] = rows
            payload["completed_count"] = len(rows)
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
        finally:
            await _save_job(job_id, payload)

    @staticmethod
    async def create_multi_model_job(
        user_id: int,
        form: Any,
        *,
        display_name: Optional[str] = None,
        eval_rounds: Optional[int] = None,
        judge_model: Optional[str] = None,
    ) -> str:
        qdir = _question_dir()
        ok, msg, _ = validate_question_dir(qdir)
        if not ok:
            raise BusinessException(ErrorCode.OPERATION_ERROR, msg)

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

        job_id = uuid.uuid4().hex
        tmpdir = eval_job_input_dir(job_id)
        model_specs: list[dict[str, Any]] = []
        total_files = 0

        try:
            os.makedirs(tmpdir, exist_ok=True)
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
                        f"模型「{model_name}」未上传 txt 文件或 zip",
                    )

                written = await ContentEvalJobService._materialize_txts(
                    dest_dir, upload_files, archive_file
                )
                if not written:
                    raise BusinessException(
                        ErrorCode.PARAMS_ERROR,
                        f"模型「{model_name}」未找到有效的 .txt 文件",
                    )
                total_files += len(written)
                model_specs.append(
                    {
                        "modelName": model_name,
                        "dirName": dir_name,
                        "fileCount": len(written),
                        "fileNames": written,
                    }
                )

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
                "model_cursor": 0,
                "partial_model_results": [],
                "completed_count": 0,
                "created_at": now,
                "finished_at": None,
                "error": None,
                "result": None,
                "api_error_count": 0,
            }
            apply_create_meta(
                payload,
                job_type="content",
                display_name=display_name,
                eval_rounds=eval_rounds,
                judge_model=judge_model,
            )
            save_input_snapshot(
                payload,
                work_dir=tmpdir,
                model_specs=model_specs,
                models=unique_names,
                job_type="multi_model",
                total_files=total_files,
                judge_model=payload.get("judge_model"),
                eval_rounds=payload.get("eval_rounds"),
                display_name=payload.get("display_name"),
            )
            await _save_job(job_id, payload)
            await _push_user_job(user_id, job_id)

            wrap_task(
                JOB_KEY_PREFIX,
                job_id,
                ContentEvalJobService._run_multi_model_job(job_id),
            )
            return job_id
        except Exception:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    @staticmethod
    async def _run_multi_model_job(job_id: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            return

        work_dir = payload.get("work_dir")
        model_specs: list[dict[str, Any]] = payload.get("model_specs") or []
        total_files = int(payload.get("total_files") or 0)
        if not work_dir or not model_specs:
            payload["status"] = "failed"
            payload["error"] = "任务输入数据已丢失"
            await _save_job(job_id, payload)
            return

        qdir = _question_dir()
        eval_rounds = int(payload.get("eval_rounds") or 1)
        judge_model = payload.get("judge_model")
        model_results: list[dict[str, Any]] = list(payload.get("partial_model_results") or [])
        model_cursor = int(payload.get("model_cursor") or 0)
        files_done = sum(
            len(m.get("perFile") or [])
            for m in model_results
        )
        total_units = max(1, total_files * eval_rounds)
        units_done = files_done * eval_rounds
        reporter = ContentEvalProgressReporter(job_id, total_units, offset=units_done)

        if files_done > 0:
            await reporter.update(units_done, message="续跑中…")

        try:
            for idx in range(model_cursor, len(model_specs)):
                spec = model_specs[idx]
                model_name = spec["modelName"]
                dir_name = spec["dirName"]
                subdir = os.path.join(work_dir, dir_name)
                file_names = spec.get("fileNames") or [
                    f for f in os.listdir(subdir) if f.lower().endswith(".txt")
                ]

                rows: list[dict[str, Any]] = []
                for file_idx, name in enumerate(file_names, start=1):
                    global_idx = files_done + file_idx
                    await reporter.update(
                        (global_idx - 1) * eval_rounds,
                        message=f"{model_name} · {idx + 1}/{len(model_specs)} · {name}",
                    )
                    row = await ContentEvalJobService._eval_one_file(
                        qdir,
                        name,
                        subdir,
                        judge_model=judge_model,
                        eval_rounds=eval_rounds,
                        payload=payload,
                    )
                    rows.append(row)
                    await reporter.update(
                        global_idx * eval_rounds,
                        message=f"{model_name} · {name}",
                    )

                summary = _compute_summary(rows)
                model_results.append(
                    {
                        "modelName": model_name,
                        "summary": summary,
                        "perFile": rows,
                    }
                )
                files_done += len(file_names)
                payload = await _load_job(job_id) or payload
                payload["partial_model_results"] = model_results
                payload["model_cursor"] = idx + 1
                payload["completed_count"] = files_done
                await _save_job(job_id, payload)
                if await check_pause_requested(_load_job, job_id, payload):
                    return

            comparison = _compute_content_model_comparison(model_results)
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
            payload.pop("partial_model_results", None)
            payload.pop("model_cursor", None)
            payload.pop("completed_count", None)
        except Exception as e:
            logger.exception("Content multi-model job %s failed", job_id)
            await reporter.finish(success=False)
            payload = await _load_job(job_id) or payload
            payload["status"] = "failed"
            payload["progress"] = int(min(99, (files_done / max(1, total_files)) * 100))
            payload["error"] = str(e)[:500]
            payload["partial_model_results"] = model_results
            payload["model_cursor"] = len(model_results)
            payload["completed_count"] = files_done
            payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
        finally:
            await _save_job(job_id, payload)

    @staticmethod
    async def get_job(job_id: str, user_id: int) -> dict[str, Any]:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看该任务")
        await ensure_estimated_cost(payload)
        if payload.get("estimated_cost_usd") is not None:
            await _save_job(job_id, payload)
        return _job_vo_from_payload(payload)

    @staticmethod
    async def update_display_name(user_id: int, job_id: str, display_name: str) -> None:
        payload = await _load_job(job_id)
        if not payload:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if payload.get("user_id") != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        await apply_display_name(payload, display_name)
        await _save_job(job_id, payload)

    @staticmethod
    async def list_jobs(user_id: int) -> list[dict[str, Any]]:
        redis = get_redis()
        job_ids = await redis.lrange(_user_jobs_key(user_id), 0, USER_JOB_LIST_MAX - 1)
        out: list[dict[str, Any]] = []
        for jid in job_ids:
            payload = await _load_job(jid)
            if payload:
                await ensure_estimated_cost(payload)
                out.append(_job_vo_from_payload(payload))
        return out
