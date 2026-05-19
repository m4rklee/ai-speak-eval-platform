from typing import Any, Dict

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.models.user import User
from app.schemas.user import LoginUserVO, UserQueryRequest, UserVO
from app.utils.password import encrypt_password


USER_LOGIN_STATE = "user_login_state"


class UserService:

    @staticmethod
    async def user_register(db: AsyncSession, user_account: str, user_password: str, check_password: str) -> int:
        # 1. 校验参数
        if not user_account or not user_password or not check_password:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "参数为空")
        if len(user_account) < 4:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "账号长度过短")
        if len(user_password) < 8 or len(check_password) < 8:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "密码长度过短")
        if user_password != check_password:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "两次输入的密码不一致")
        
        # 2.检查账号是否重复
        result = await db.execute(
            select(User).where(User.user_account == user_account, User.is_delete == 0)
        )
        if result.scalar_one_or_none():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "账号重复")
        
        # 3.密码加密
        encrypt_pwd = encrypt_password(user_password)

        # 4.插入数据
        new_user = User(
            user_account=user_account,
            user_password=encrypt_pwd,
            user_name="无名",
            user_role="user"
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user.id

    @staticmethod
    async def user_login(
        db: AsyncSession,
        request: Request,
        user_account: str,
        user_password: str
    ) -> LoginUserVO:
        # 1.校验
        if not user_account or not user_password:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "参数为空")

        # 2.加密后查询
        encrypt_pwd = encrypt_password(user_password)
        result = await db.execute(
            select(User).where(
                User.user_account == user_account,
                User.user_password == encrypt_pwd,
                User.is_delete == 0
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "用户不存在或密码错误")

        # 3.记录登录态到Session
        request.state.session[USER_LOGIN_STATE] = {
            "id": user.id,
            "user_account": user.user_account,
            "user_role": user.user_role
        }

        # 4.返回脱敏后的用户信息
        return LoginUserVO.model_validate(user)

    @staticmethod
    async def get_login_user(db: AsyncSession, request: Request) -> User:
        # 从Session中获取用户信息
        user_info = request.state.session.get(USER_LOGIN_STATE)
        if not user_info or not user_info.get("id"):
            raise BusinessException(ErrorCode.NOT_LOGIN_ERROR)

        # 从数据库查询最新数据
        user_id = user_info["id"]
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_delete == 0)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise BusinessException(ErrorCode.NOT_LOGIN_ERROR)
        return user

    @staticmethod
    def get_login_user_vo(user: User) -> LoginUserVO:
        return LoginUserVO.model_validate(user)

    @staticmethod
    async def user_logout(request: Request) -> bool:
        if USER_LOGIN_STATE not in request.state.session:
            raise BusinessException(ErrorCode.OPERATION_ERROR, '未登录')
        request.state.session.pop(USER_LOGIN_STATE, None)
        return True

    @staticmethod
    async def check_admin(db: AsyncSession, request: Request):
        user = await UserService.get_login_user(db, request)
        if user.user_role != "admin":
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")

    @staticmethod
    async def delete_user(db: AsyncSession, user_id: int) -> bool:
        if user_id <= 0:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "用户ID无效")

        result = await db.execute(
            select(User).where(User.id == user_id, User.is_delete == 0)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "用户不存在")

        user.is_delete = 1
        await db.commit()
        return True

    @staticmethod
    async def list_user_vo_by_page(db: AsyncSession, query_request: UserQueryRequest) -> Dict[str, Any]:
        # 构建查询条件
        query = select(User).where(User.is_delete == 0)
        if query_request.user_account:
            query = query.where(User.user_account.like(f"%{query_request.user_account}%"))
        if query_request.user_name:
            query = query.where(User.user_name.like(f"%{query_request.user_name}%"))
        if query_request.user_role:
            query = query.where(User.user_role == query_request.user_role)

        # 查询总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页查询
        offset = (query_request.current - 1) * query_request.page_size
        query = query.offset(offset).limit(query_request.page_size)
        users = (await db.execute(query)).scalars().all()

        # 转换为VO
        user_vo_list = [UserVO.model_validate(user) for user in users]
        return {
            "records": [vo.model_dump(by_alias=True) for vo in user_vo_list],
            "total": total,
            "current": query_request.current,
            "pageSize": query_request.page_size
        }
