"""综合评测 API：wav + txt 成对，并行语音 Uni + 内容 Judge；支持一站式回复生成流水线。"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.eval_job_common import EvalJobDisplayNameUpdateVO
from app.schemas.oral_combined_eval import (
    OralCombinedFromOralGenVO,
    OralCombinedHealthVO,
    OralCombinedJobListVO,
    OralCombinedJobVO,
    OralCombinedPipelineCreateVO,
)
from app.services.oral_combined_eval_job_service import OralCombinedEvalJobService
from app.services.user_service import UserService

router = APIRouter(prefix="/oral-combined", tags=["综合评测"])


@router.get("/health", response_model=BaseResponse[OralCombinedHealthVO], summary="综合评测状态")
async def oral_combined_health():
    data = await OralCombinedEvalJobService.health_async()
    return BaseResponse(
        code=0,
        data=OralCombinedHealthVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.post("/jobs", response_model=BaseResponse[str], summary="创建综合评测任务（上传答案对）")
async def create_job(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    files: list[UploadFile] = File(default=[]),
    archive: Optional[UploadFile] = File(default=None),
    display_name: Optional[str] = Form(default=None, alias="displayName"),
    eval_rounds: Optional[int] = Form(default=None, alias="evalRounds"),
    judge_model: Optional[str] = Form(default=None, alias="judgeModel"),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralCombinedEvalJobService.create_job(
        user.id,
        files,
        archive,
        display_name=display_name,
        eval_rounds=eval_rounds,
        judge_model=judge_model,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post(
    "/jobs/pipeline",
    response_model=BaseResponse[str],
    summary="创建一站式任务（回复生成 + 综合评测）",
)
async def create_pipeline_job(
    request: Request,
    body: OralCombinedPipelineCreateVO,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralCombinedEvalJobService.create_pipeline_job(
        user.id,
        model=body.model,
        source=body.source,  # type: ignore[arg-type]
        sample_mode=body.sample_mode,  # type: ignore[arg-type]
        sample_count=body.sample_count,
        seed=body.seed,
        request_interval=body.request_interval,
        auto_start_eval=body.auto_start_eval,
        display_name=body.display_name,
        eval_rounds=body.eval_rounds,
        judge_model=body.judge_model,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post(
    "/jobs/pipeline/upload",
    response_model=BaseResponse[str],
    summary="创建一站式任务（上传题目 wav）",
)
async def create_pipeline_job_upload(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    model: str = Form(...),
    auto_start_eval: bool = Form(default=True),
    request_interval: Optional[float] = Form(default=None),
    display_name: Optional[str] = Form(default=None, alias="displayName"),
    eval_rounds: Optional[int] = Form(default=None, alias="evalRounds"),
    judge_model: Optional[str] = Form(default=None, alias="judgeModel"),
    files: list[UploadFile] = File(...),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralCombinedEvalJobService.create_pipeline_job(
        user.id,
        model=model,
        source="upload",
        auto_start_eval=auto_start_eval,
        request_interval=request_interval,
        files=files,
        display_name=display_name,
        eval_rounds=eval_rounds,
        judge_model=judge_model,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post(
    "/jobs/from-oral-gen/{oral_gen_job_id}",
    response_model=BaseResponse[str],
    summary="从回复生成任务导入并综合评测",
)
async def create_from_oral_gen(
    oral_gen_job_id: str,
    request: Request,
    body: OralCombinedFromOralGenVO,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralCombinedEvalJobService.create_from_oral_gen(
        user.id,
        oral_gen_job_id,
        auto_start_eval=body.auto_start_eval,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post(
    "/jobs/{job_id}/resume",
    response_model=BaseResponse[None],
    summary="续跑已中断或待评测的综合评测任务",
)
async def resume_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await OralCombinedEvalJobService.resume_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/pause",
    response_model=BaseResponse[None],
    summary="暂停综合评测任务",
)
async def pause_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await OralCombinedEvalJobService.pause_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/rerun",
    response_model=BaseResponse[None],
    summary="重跑综合评测任务",
)
async def rerun_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await OralCombinedEvalJobService.rerun_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/continue",
    response_model=BaseResponse[None],
    summary="一站式：预览后继续综合评测",
)
async def continue_pipeline_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await OralCombinedEvalJobService.continue_pipeline(job_id, user.id)
    return BaseResponse(code=0, data=None, message="ok")


@router.get(
    "/jobs",
    response_model=BaseResponse[OralCombinedJobListVO],
    summary="当前用户最近综合评测任务",
)
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    jobs = await OralCombinedEvalJobService.list_jobs(user.id)
    vo = OralCombinedJobListVO(
        jobs=[OralCombinedJobVO.model_validate(j) for j in jobs],
    )
    return BaseResponse(
        code=0,
        data=vo.model_dump(by_alias=True),
        message="ok",
    )


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
    await OralCombinedEvalJobService.update_display_name(user.id, job_id, body.display_name)
    return BaseResponse(code=0, data=None, message="ok")


@router.get(
    "/jobs/{job_id}",
    response_model=BaseResponse[OralCombinedJobVO],
    summary="查询综合评测任务",
)
async def get_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await OralCombinedEvalJobService.get_job(job_id, user.id)
    return BaseResponse(
        code=0,
        data=OralCombinedJobVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/jobs/{job_id}/audio/{filename}",
    summary="播放综合任务中的 wav",
)
async def get_job_audio(
    job_id: str,
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    path = await OralCombinedEvalJobService.get_job_audio_path(job_id, user.id, filename)
    return FileResponse(path, media_type="audio/wav", filename=os.path.basename(path))
