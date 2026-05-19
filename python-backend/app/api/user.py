from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse, DeleteRequest
from app.schemas.user import LoginUserVO, UserLoginRequest, UserQueryRequest, UserRegisterRequest
from app.services.user_service import UserService


router = APIRouter(prefix="/user", tags=["用户接口"])

@router.post("/register", response_model=BaseResponse[int], summary="用户注册")
async def user_register(request: UserRegisterRequest, db: AsyncSession = Depends(get_async_db)):
    user_id = await UserService.user_register(db, request.user_account, request.user_password, request.check_password)
    return BaseResponse(code=0, data=user_id, message="ok")

@router.post("/login", response_model=BaseResponse[LoginUserVO], summary="用户登录")
async def user_login(login_request: UserLoginRequest, request: Request, db: AsyncSession = Depends(get_async_db)):
    login_user = await UserService.user_login(db, request, login_request.user_account, login_request.user_password)
    return BaseResponse(code=0, data=login_user, message="ok")

@router.get("/get/login", response_model=BaseResponse[LoginUserVO], summary="获取当前登录用户")
async def get_login_user(request: Request, db: AsyncSession = Depends(get_async_db)):
    user = await UserService.get_login_user(db, request)
    login_user_vo = UserService.get_login_user_vo(user)
    return BaseResponse(code=0, data=login_user_vo, message="ok")

@router.post("/logout", response_model=BaseResponse[bool], summary="用户登出")
async def user_logout(request: Request):
    result = await UserService.user_logout(request)
    return BaseResponse(code=0, data=result, message="ok")

@router.post('/delete', response_model=BaseResponse[bool], summary="删除用户（管理员）")
async def delete_user(delete_request: DeleteRequest, request: Request, db: AsyncSession = Depends(get_async_db)):
    await UserService.check_admin(db, request)
    result = await UserService.delete_user(db, delete_request.id)
    return BaseResponse(code=0, data=result, message="ok")

@router.post("/list/page/vo", response_model=BaseResponse[dict], summary="分页查询用户（管理员）")
async def list_user_vo_by_page(query_request: UserQueryRequest, request: Request, db: AsyncSession = Depends(get_async_db)):
    await UserService.check_admin(db, request)
    page_result = await UserService.list_user_vo_by_page(db, query_request)
    return BaseResponse(code=0, data=page_result, message="ok")
