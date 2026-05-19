from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.batch import BatchJobCreateRequest, BatchJobListQuery, BatchResultQuery
from app.schemas.common import BaseResponse
from app.services.batch_job_service import BatchJobService
from app.services.user_service import UserService


router = APIRouter(prefix="/batch", tags=["批量评测"])


@router.post("/job/create", response_model=BaseResponse[str], summary="创建批量评测任务")
async def create_batch_job(
    body: BatchJobCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    job_id = await BatchJobService(db).create_job(body, user.id)
    return BaseResponse(code=0, data=job_id, message="ok")


@router.get("/job/list", response_model=BaseResponse[dict], summary="任务列表")
async def list_batch_jobs(
    request: Request,
    query: BatchJobListQuery = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    page = await BatchJobService(db).list_jobs(user.id, query.current, query.page_size)
    return BaseResponse(code=0, data=page, message="ok")


@router.get("/job/{job_id}", response_model=BaseResponse[dict], summary="任务详情")
async def get_batch_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    job = await BatchJobService(db).get_job(job_id, user.id)
    return BaseResponse(code=0, data=job.model_dump(by_alias=True), message="ok")


@router.get("/job/{job_id}/results", response_model=BaseResponse[dict], summary="任务结果列表")
async def list_batch_results(
    job_id: str,
    request: Request,
    query: BatchResultQuery = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    page = await BatchJobService(db).list_results(
        job_id, user.id, query.current, query.page_size,
        query.model_name, query.status
    )
    return BaseResponse(code=0, data=page, message="ok")


@router.post("/job/{job_id}/score", response_model=BaseResponse[bool], summary="对已完成任务执行/重跑评分")
async def score_batch_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await BatchJobService(db).score_job(job_id, user.id)
    return BaseResponse(code=0, data=True, message="ok")


@router.post("/job/{job_id}/cancel", response_model=BaseResponse[bool], summary="取消任务")
async def cancel_batch_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    result = await BatchJobService(db).cancel_job(job_id, user.id)
    return BaseResponse(code=0, data=result, message="ok")


@router.get("/job/{job_id}/export", summary="导出任务结果为 ZIP")
async def export_batch_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    data = await BatchJobService(db).export_job_zip(job_id, user.id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="batch_{job_id}.zip"'},
    )
