"""北极星听力评测 API。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.listen_eval import (
    ListenEvalHealthVO,
    ListenEvalJobCreateVO,
    ListenEvalJobListVO,
    ListenEvalJobVO,
)
from app.services.listen_eval_job_service import ListenEvalJobService
from app.services.user_service import UserService

router = APIRouter(prefix="/listen-eval", tags=["听力评测"])


@router.get("/health", response_model=BaseResponse[ListenEvalHealthVO], summary="听力评测状态")
async def listen_eval_health():
    data = ListenEvalJobService.health()
    return BaseResponse(
        code=0,
        data=ListenEvalHealthVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.post("/jobs", response_model=BaseResponse[str], summary="创建听力评测任务")
async def create_job(
    body: ListenEvalJobCreateVO,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    job_id = await ListenEvalJobService.create_job(
        user.id,
        model=body.model,
        sample_mode=body.sample_mode,
        sample_count=body.sample_count,
        seed=body.seed,
        request_interval=body.request_interval,
        workers=body.workers,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.get(
    "/jobs",
    response_model=BaseResponse[ListenEvalJobListVO],
    summary="当前用户最近听力评测任务",
)
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    jobs = await ListenEvalJobService.list_jobs(user.id)
    vo = ListenEvalJobListVO(
        jobs=[ListenEvalJobVO.model_validate(j) for j in jobs],
    )
    return BaseResponse(
        code=0,
        data=vo.model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=BaseResponse[ListenEvalJobVO],
    summary="查询听力评测任务",
)
async def get_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await ListenEvalJobService.get_job(job_id, user.id)
    return BaseResponse(
        code=0,
        data=ListenEvalJobVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )
