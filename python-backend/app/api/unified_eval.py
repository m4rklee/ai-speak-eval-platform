"""Uni 统一语音评测专用 API（MultiPA + APG-MOS）。"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.eval_job_common import EvalJobDisplayNameUpdateVO
from app.schemas.unified_eval import (
    UnifiedEvalHealthVO,
    UnifiedEvalJobListVO,
    UnifiedEvalJobVO,
    UnifiedEvalSingleResultVO,
)
from app.services.oral_eval import unified_eval_daemon_manager as daemon_mgr
from app.services.oral_eval.unified_eval_runner import validate_unified_eval_paths
from app.services.unified_eval_job_service import UnifiedEvalJobService
from app.services.user_service import UserService

router = APIRouter(prefix="/unified-eval", tags=["Uni统一语音评测"])


@router.get("/health", response_model=BaseResponse[UnifiedEvalHealthVO], summary="评测引擎状态")
async def unified_eval_health():
    paths_ok, paths_msg = validate_unified_eval_paths()
    daemon_ok = await daemon_mgr.daemons_healthy()
    daemon_managed = daemon_mgr.daemons_running()
    data = UnifiedEvalHealthVO(
        unified_eval_enabled=get_settings().UNIFIED_EVAL_ENABLED,
        use_daemon=True,
        paths_ok=paths_ok,
        paths_message=paths_msg if paths_ok else paths_msg,
        daemon_running=daemon_managed or daemon_ok,
        daemon_ready=daemon_ok,
        multipa_port=get_settings().MULTIPA_DAEMON_PORT,
        apg_port=get_settings().APG_DAEMON_PORT,
        engine="daemon",
    )
    if paths_ok and not daemon_ok:
        data = data.model_copy(
            update={
                "paths_message": (
                    f"{paths_msg}; " if paths_msg else ""
                ) + "评测 daemon 未就绪，请执行 bash scripts/eval-daemons.sh restart",
            }
        )
    else:
        data = data.model_copy(update={"paths_message": paths_msg})
    return BaseResponse(code=0, data=data.model_dump(by_alias=True), message="ok")


@router.post(
    "/evaluate",
    response_model=BaseResponse[UnifiedEvalSingleResultVO],
    summary="单文件同步评测",
)
async def evaluate_single(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await UnifiedEvalJobService.evaluate_single(file, user.id)
    return BaseResponse(
        code=0,
        data=UnifiedEvalSingleResultVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.post("/jobs", response_model=BaseResponse[str], summary="创建批量评测任务")
async def create_job(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    files: list[UploadFile] = File(default=[]),
    archive: Optional[UploadFile] = File(default=None),
    display_name: Optional[str] = Form(default=None, alias="displayName"),
    eval_rounds: Optional[int] = Form(default=None, alias="evalRounds"),
):
    user = await UserService.get_login_user(db, request)
    job_id = await UnifiedEvalJobService.create_job(
        user.id,
        files,
        archive,
        display_name=display_name,
        eval_rounds=eval_rounds,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post("/multi-model-jobs", response_model=BaseResponse[str], summary="创建多模型对比评测任务")
async def create_multi_model_job(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    form = await request.form()
    display_name = form.get("displayName")
    eval_rounds_raw = form.get("evalRounds")
    eval_rounds = int(eval_rounds_raw) if eval_rounds_raw not in (None, "") else None
    job_id = await UnifiedEvalJobService.create_multi_model_job(
        user.id,
        form,
        display_name=str(display_name).strip() if display_name else None,
        eval_rounds=eval_rounds,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.get(
    "/jobs",
    response_model=BaseResponse[UnifiedEvalJobListVO],
    summary="当前用户最近任务列表",
)
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    jobs = await UnifiedEvalJobService.list_jobs(user.id)
    vo = UnifiedEvalJobListVO(
        jobs=[UnifiedEvalJobVO.model_validate(j) for j in jobs],
    )
    return BaseResponse(
        code=0,
        data=vo.model_dump(by_alias=True),
        message="ok",
    )


@router.post(
    "/jobs/{job_id}/resume",
    response_model=BaseResponse[None],
    summary="续跑已中断的语音评测任务",
)
async def resume_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await UnifiedEvalJobService.resume_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/pause",
    response_model=BaseResponse[None],
    summary="暂停语音评测任务",
)
async def pause_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await UnifiedEvalJobService.pause_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/rerun",
    response_model=BaseResponse[None],
    summary="重跑语音评测任务",
)
async def rerun_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await UnifiedEvalJobService.rerun_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.patch(
    "/jobs/{job_id}/display-name",
    response_model=BaseResponse[None],
    summary="更新任务显示名称",
)
async def update_display_name(
    job_id: str,
    body: EvalJobDisplayNameUpdateVO,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await UnifiedEvalJobService.update_display_name(user.id, job_id, body.display_name)
    return BaseResponse(code=0, data=None, message="ok")


@router.get(
    "/jobs/{job_id}",
    response_model=BaseResponse[UnifiedEvalJobVO],
    summary="查询任务状态与结果",
)
async def get_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await UnifiedEvalJobService.get_job(job_id, user.id)
    return BaseResponse(
        code=0,
        data=UnifiedEvalJobVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/jobs/{job_id}/audio/{filename}",
    summary="播放任务中的 wav 音频",
)
async def get_job_audio(
    job_id: str,
    filename: str,
    request: Request,
    model_name: Optional[str] = Query(default=None, alias="modelName"),
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    path = await UnifiedEvalJobService.get_job_audio_path(
        job_id, user.id, filename, model_name=model_name
    )
    return FileResponse(path, media_type="audio/wav", filename=os.path.basename(path))

