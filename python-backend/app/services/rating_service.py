"""
用户评分服务
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.models.conversation import Conversation
from app.models.rating import Rating
from app.schemas.rating import RatingRequest


class RatingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_rating(self, request: RatingRequest, user_id: int) -> bool:
        """保存或更新用户评分"""
        if request.rating_type not in {"model_better", "tie", "both_bad"}:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "评分类型错误")

        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user_id,
                Conversation.is_delete == 0
            )
        )
        if not result.scalar_one_or_none():
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "对话不存在")

        result = await self.db.execute(
            select(Rating).where(
                Rating.conversation_id == request.conversation_id,
                Rating.message_index == request.message_index,
                Rating.user_id == user_id,
                Rating.is_delete == 0
            )
        )
        rating = result.scalar_one_or_none()

        if rating:
            rating.rating_type = request.rating_type
            rating.winner_model = request.winner_model
            rating.loser_model = request.loser_model
        else:
            self.db.add(Rating(
                id=str(uuid.uuid4()),
                conversation_id=request.conversation_id,
                message_index=request.message_index,
                user_id=user_id,
                rating_type=request.rating_type,
                winner_model=request.winner_model,
                loser_model=request.loser_model,
                is_delete=0
            ))

        await self.db.commit()
        return True
