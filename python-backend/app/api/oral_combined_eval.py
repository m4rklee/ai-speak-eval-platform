"""综合评测 API：wav + txt 成对，并行语音 Uni + 内容 Judge。"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.oral_combined_eval import (
    OralCombinedHealthVO,
    OralCombinedJobListVO,
    OralCombinedJobVO,
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


@router.post("/jobs", response_model=BaseResponse[str], summary="创建综合评测任务")
async def create_job(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    files: list[UploadFile] = File(default=[]),
    archive: Optional[UploadFile] = File(default=None),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralCombinedEvalJobService.create_job(user.id, files, archive)
    return BaseResponse(code=0, data=job_id, message="ok")


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
