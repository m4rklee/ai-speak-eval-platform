"""
简单 Redis 限流工具
"""
from enum import Enum

from fastapi import Request
from redis.asyncio import Redis

from app.core.errors import BusinessException, ErrorCode


class RateLimitType(Enum):
    """限流类型"""
    USER = "user"


async def check_rate_limit(
    redis_client: Redis,
    request: Request,
    limit_type: RateLimitType,
    limit: int,
    window_seconds: int,
    message: str,
    identifier: str | int | None = None
) -> None:
    """固定窗口限流"""
    if identifier is None:
        identifier = request.client.host if request.client else "unknown"

    key = f"rate_limit:{limit_type.value}:{identifier}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)

    if current > limit:
        raise BusinessException(ErrorCode.OPERATION_ERROR, message)
