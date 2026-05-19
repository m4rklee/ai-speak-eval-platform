from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.scenario import (
    PageQueryRequest,
    ScenarioAddRequest,
    ScenarioImportRequest,
    ScenarioItemUpdateRequest,
    ScenarioUpdateRequest,
    ScenarioVO,
)
from app.services.scenario_service import ScenarioService
from app.services.user_service import UserService


router = APIRouter(prefix="/scenario", tags=["场景管理"])


@router.get("/list", response_model=BaseResponse[list], summary="场景列表")
async def list_scenarios(request: Request, db: AsyncSession = Depends(get_async_db)):
    user = await UserService.get_login_user(db, request)
    scenarios = await ScenarioService(db).list_scenarios(user.id)
    return BaseResponse(code=0, data=[s.model_dump(by_alias=True) for s in scenarios], message="ok")


@router.get("/{scenario_id}", response_model=BaseResponse[dict], summary="场景详情")
async def get_scenario(
    scenario_id: str,
    request: Request,
    current: int = 1,
    pageSize: int = 50,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    detail = await ScenarioService(db).get_scenario_detail(scenario_id, user.id, current, pageSize)
    return BaseResponse(code=0, data=detail, message="ok")


@router.post("/add", response_model=BaseResponse[str], summary="创建自定义场景")
async def add_scenario(
    body: ScenarioAddRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    scenario_id = await ScenarioService(db).add_scenario(body, user.id)
    return BaseResponse(code=0, data=scenario_id, message="ok")


@router.put("/{scenario_id}", response_model=BaseResponse[bool], summary="更新场景")
async def update_scenario(
    scenario_id: str,
    body: ScenarioUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    result = await ScenarioService(db).update_scenario(scenario_id, body, user.id)
    return BaseResponse(code=0, data=result, message="ok")


@router.delete("/{scenario_id}", response_model=BaseResponse[bool], summary="删除场景")
async def delete_scenario(
    scenario_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    result = await ScenarioService(db).delete_scenario(scenario_id, user.id)
    return BaseResponse(code=0, data=result, message="ok")


@router.post("/{scenario_id}/import", response_model=BaseResponse[int], summary="导入用例JSON")
async def import_scenario_items(
    scenario_id: str,
    body: ScenarioImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    count = await ScenarioService(db).import_items(scenario_id, body, user.id)
    return BaseResponse(code=0, data=count, message="ok")


@router.get("/{scenario_id}/items", response_model=BaseResponse[dict], summary="分页查询用例")
async def list_scenario_items(
    scenario_id: str,
    request: Request,
    query: PageQueryRequest = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    page = await ScenarioService(db).list_items(
        scenario_id, user.id, query.current, query.page_size
    )
    return BaseResponse(code=0, data=page, message="ok")


@router.put("/item/{item_id}", response_model=BaseResponse[bool], summary="更新用例")
async def update_scenario_item(
    item_id: str,
    body: ScenarioItemUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    result = await ScenarioService(db).update_item(item_id, body, user.id)
    return BaseResponse(code=0, data=result, message="ok")


@router.delete("/item/{item_id}", response_model=BaseResponse[bool], summary="删除用例")
async def delete_scenario_item(
    item_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = await UserService.get_login_user(db, request)
    result = await ScenarioService(db).delete_item(item_id, user.id)
    return BaseResponse(code=0, data=result, message="ok")
