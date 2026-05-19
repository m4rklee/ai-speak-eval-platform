"""
用户评分接口
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.rating import RatingRequest
from app.services.rating_service import RatingService
from app.services.user_service import UserService


router = APIRouter(prefix="/rating", tags=["用户评分接口"])


@router.post("/add", response_model=BaseResponse[bool], summary="保存用户评分")
async def add_rating(
    rating_request: RatingRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    login_user = await UserService.get_login_user(db, request)
    result = await RatingService(db).add_rating(rating_request, login_user.id)
    return BaseResponse(code=0, data=result, message="ok")
