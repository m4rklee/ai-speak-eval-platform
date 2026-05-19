from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.conversation import VoiceEvalRequest, VoiceScoreRequest
from app.services.oral_eval.oral_scoring_service import OralScoringService
from app.services.user_service import UserService
from app.services.voice_service import VoiceEvalService

router = APIRouter(prefix="/voice", tags=["语音评测"])


@router.post("/eval/stream", summary="单模型语音评测 SSE")
async def voice_eval_stream(
    body: VoiceEvalRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    service = VoiceEvalService(db)

    async def event_generator():
        async for event in service.eval_stream(body, user.id):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/eval/score", summary="单条口语评分")
async def voice_eval_score(
    body: VoiceScoreRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    _ = user
    service = OralScoringService(db)
    detail = await service.score_inline(
        prompt=body.prompt,
        expected_answer=body.expected_answer,
        output_content=body.output_content,
        output_audio=body.output_audio,
        eval_cfg=body.eval_config,
    )
    return BaseResponse(code=0, data=detail, message="ok")
