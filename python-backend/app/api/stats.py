from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.services.stats_service import StatsService
from app.services.user_service import UserService


router = APIRouter(prefix="/stats", tags=["统计分析"])


@router.get("/model", response_model=BaseResponse[list], summary="全平台模型统计")
async def list_model_stats(
    sortBy: str = "totalTokens",
    db: AsyncSession = Depends(get_async_db)
):
    stats = await StatsService(db).list_model_stats(sortBy)
    return BaseResponse(code=0, data=[s.model_dump(by_alias=True) for s in stats], message="ok")


@router.get("/user/me", response_model=BaseResponse[list], summary="当前用户模型使用统计")
async def list_my_model_stats(request: Request, db: AsyncSession = Depends(get_async_db)):
    user = await UserService.get_login_user(db, request)
    stats = await StatsService(db).list_user_model_stats(user.id)
    return BaseResponse(code=0, data=[s.model_dump(by_alias=True) for s in stats], message="ok")


@router.get("/user/me/summary", response_model=BaseResponse[dict], summary="当前用户使用汇总")
async def get_my_stat_summary(request: Request, db: AsyncSession = Depends(get_async_db)):
    user = await UserService.get_login_user(db, request)
    summary = await StatsService(db).get_user_summary(user.id)
    return BaseResponse(code=0, data=summary.model_dump(by_alias=True), message="ok")
