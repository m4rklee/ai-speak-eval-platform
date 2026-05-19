from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.model import ModelListQuery, ModelVO
from app.services.model_service import ModelService
from app.services.user_service import UserService


router = APIRouter(prefix="/model", tags=["模型接口"])


@router.post("/sync", response_model=BaseResponse[dict], summary="同步模型列表（管理员）")
async def sync_models(
    request: Request,
    platform: str = Query(default="all", description="openrouter|aihubmix|all"),
    db: AsyncSession = Depends(get_async_db),
):
    await UserService.check_admin(db, request)
    counts = await ModelService(db).sync_models(platform)
    return BaseResponse(code=0, data=counts, message="ok")


@router.post("/sync/openrouter", response_model=BaseResponse[int], summary="从 OpenRouter 同步（兼容旧接口）")
async def sync_models_from_openrouter(request: Request, db: AsyncSession = Depends(get_async_db)):
    await UserService.check_admin(db, request)
    synced_count = await ModelService(db).sync_models_from_openrouter()
    return BaseResponse(code=0, data=synced_count, message="ok")


@router.get("/list", response_model=BaseResponse[list], summary="查询模型列表（支持筛选）")
async def list_models(
    query: ModelListQuery = Depends(),
    db: AsyncSession = Depends(get_async_db),
):
    models = await ModelService(db).list_models(query)
    return BaseResponse(code=0, data=[m.model_dump(by_alias=True) for m in models], message="ok")


@router.get("/platforms", response_model=BaseResponse[list], summary="支持的平台列表")
async def list_platforms_api():
    from app.providers.registry import list_platforms
    return BaseResponse(code=0, data=list_platforms(), message="ok")
