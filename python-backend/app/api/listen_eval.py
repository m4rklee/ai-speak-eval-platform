"""北极星听力评测 API。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.eval_job_common import EvalJobDisplayNameUpdateVO, EvalJobRuntimeOptionsVO
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
        display_name=body.display_name,
        eval_rounds=body.eval_rounds,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


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
    await ListenEvalJobService.update_display_name(user.id, job_id, body.display_name)
    return BaseResponse(code=0, data=None, message="ok")


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


@router.post(
    "/jobs/{job_id}/resume",
    response_model=BaseResponse[None],
    summary="续跑已中断的听力评测任务",
)
async def resume_job(
    job_id: str,
    request: Request,
    body: EvalJobRuntimeOptionsVO | None = None,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    opts = body or EvalJobRuntimeOptionsVO()
    await ListenEvalJobService.resume_job(
        user.id,
        job_id,
        workers=opts.workers,
        request_interval=opts.request_interval,
    )
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/pause",
    response_model=BaseResponse[None],
    summary="暂停听力评测任务",
)
async def pause_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await ListenEvalJobService.pause_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/rerun",
    response_model=BaseResponse[None],
    summary="重跑听力评测任务",
)
async def rerun_job(
    job_id: str,
    request: Request,
    body: EvalJobRuntimeOptionsVO | None = None,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    opts = body or EvalJobRuntimeOptionsVO()
    await ListenEvalJobService.rerun_job(
        user.id,
        job_id,
        workers=opts.workers,
        request_interval=opts.request_interval,
        skip_completed=bool(opts.skip_completed),
    )
    return BaseResponse(code=0, data=None, message="ok")
