"""
对话接口
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.db.redis import get_redis
from app.db.session import get_async_db
from app.schemas.conversation import GenerateVariantsRequest, PromptLabRequest, SideBySideRequest
from app.schemas.common import BaseResponse
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.user_service import UserService
from app.utils.rate_limiter import RateLimitType, check_rate_limit


router = APIRouter(prefix="/conversation", tags=["对话接口"])


@router.post("/side-by-side/stream", summary="Side-by-Side 多模型并排对比")
async def side_by_side_stream(
    side_by_side_request: SideBySideRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    login_user = await UserService.get_login_user(db, request)
    await check_rate_limit(
        get_redis(), request,
        RateLimitType.USER, 5, 60,
        message="AI 对话请求过于频繁，请稍后再试",
        identifier=login_user.id
    )

    conversation_service = ConversationService(db)
    conversation_service.validate_side_by_side_request(side_by_side_request)
    return StreamingResponse(
        conversation_service.side_by_side_stream(side_by_side_request, login_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/prompt-lab/stream", summary="Prompt Lab 提示词变体对比")
async def prompt_lab_stream(
    prompt_lab_request: PromptLabRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    login_user = await UserService.get_login_user(db, request)
    await check_rate_limit(
        get_redis(), request,
        RateLimitType.USER, 5, 60,
        message="AI 对话请求过于频繁，请稍后再试",
        identifier=login_user.id
    )

    conversation_service = ConversationService(db)
    conversation_service.validate_prompt_lab_request(prompt_lab_request)
    return StreamingResponse(
        conversation_service.prompt_lab_stream(prompt_lab_request, login_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/generate-variants", response_model=BaseResponse[list[str]], summary="自动生成提示词变体")
async def generate_variants(
    generate_request: GenerateVariantsRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    login_user = await UserService.get_login_user(db, request)
    await check_rate_limit(
        get_redis(), request,
        RateLimitType.USER, 10, 60,
        message="变体生成请求过于频繁，请稍后再试",
        identifier=login_user.id
    )

    variants = await ChatService.generate_variants(
        prompt=generate_request.prompt,
        count=generate_request.count,
        model_name=generate_request.model or "deepseek/deepseek-chat"
    )
    return BaseResponse(code=0, data=variants, message="ok")
