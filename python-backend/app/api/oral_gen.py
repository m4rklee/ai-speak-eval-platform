"""口语回复生成 API。"""
import os

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.oral_gen import (
    OralGenHealthVO,
    OralGenJobCreateVO,
    OralGenJobListVO,
    OralGenJobVO,
)
from app.services.oral_gen_job_service import OralGenJobService, _job_dir
from app.services.user_service import UserService

router = APIRouter(prefix="/oral-gen", tags=["口语回复生成"])


@router.get("/health", response_model=BaseResponse[OralGenHealthVO], summary="回复生成状态")
async def oral_gen_health():
    data = OralGenJobService.health()
    return BaseResponse(
        code=0,
        data=OralGenHealthVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.post("/jobs", response_model=BaseResponse[str], summary="创建回复生成任务（内置数据集）")
async def create_job_builtin(
    body: OralGenJobCreateVO,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralGenJobService.create_job_builtin(
        user.id,
        model=body.model,
        sample_mode=body.sample_mode,
        sample_count=body.sample_count,
        seed=body.seed,
        request_interval=body.request_interval,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post("/jobs/upload", response_model=BaseResponse[str], summary="创建回复生成任务（上传音频）")
async def create_job_upload(
    request: Request,
    model: str = Form(...),
    request_interval: float | None = Form(default=None),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    job_id = await OralGenJobService.create_job_upload(
        user.id,
        model=model,
        files=files,
        request_interval=request_interval,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.get(
    "/jobs",
    response_model=BaseResponse[OralGenJobListVO],
    summary="当前用户最近回复生成任务",
)
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    jobs = await OralGenJobService.list_jobs(user.id)
    vo = OralGenJobListVO(jobs=[OralGenJobVO.model_validate(j) for j in jobs])
    return BaseResponse(
        code=0,
        data=vo.model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=BaseResponse[OralGenJobVO],
    summary="查询回复生成任务",
)
async def get_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await OralGenJobService.get_job(job_id, user.id)
    return BaseResponse(
        code=0,
        data=OralGenJobVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/jobs/{job_id}/audio/{stem}",
    summary="获取生成音频 wav",
)
async def get_job_audio(
    job_id: str,
    stem: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await OralGenJobService.assert_job_access(job_id, user.id)
    safe_stem = stem.replace("/", "_").replace("\\", "_").replace("..", "_")
    path = os.path.join(_job_dir(job_id), "audio", f"{safe_stem}.wav")
    if not os.path.isfile(path):
        from app.core.errors import BusinessException, ErrorCode

        raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "音频不存在")
    return FileResponse(path, media_type="audio/wav", filename=f"{safe_stem}.wav")


@router.get("/jobs/{job_id}/export", summary="导出 ZIP（audio/ + text/）")
async def export_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await OralGenJobService.build_export_zip(job_id, user.id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="oral-gen-{job_id}.zip"'
        },
    )
