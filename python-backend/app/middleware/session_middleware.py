from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.db.redis_session import RedisSessionBackend


settings = get_settings()


class RedisSessionMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        session_backend: RedisSessionBackend,
        cookie_name: str = "session_id",
        max_age: int | None = None,
    ):
        super().__init__(app)
        self.session_backend = session_backend
        self.cookie_name = cookie_name
        self.max_age = max_age or settings.COOKIE_MAX_AGE

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. 从 Cookie 中获取 session_id
        session_id = request.cookies.get(self.cookie_name)
        session_backend = self.session_backend

        # 2. 从 Redis 加载 Session 数据
        if session_id and await session_backend.exists(session_id):
            session_data = await session_backend.get(session_id)

        else:
            session_id = session_backend.generate_session_id()
            session_data = {}

        # 3.将 Session 挂载到 request.state 上
        request.state.session = SessionProxy(session_data, session_backend, session_id)

        # 4.处理请求
        response = await call_next(request)

        # 5.保存修改后的 Session 到 Redis
        await request.state.session.save()

        # 6.设置Cookie
        response.set_cookie(
            key=self.cookie_name,
            value=session_id,
            max_age=self.max_age,
            httponly=True,
            path='/'
        )
        return response


class SessionProxy(dict):
    def __init__(self, data: dict, backend: RedisSessionBackend, session_id: str):
        super().__init__(data or {})
        self._backend = backend
        self._session_id = session_id

    async def save(self) -> None:
        await self._backend.set(self._session_id, dict(self))
