from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.models.user_model_stat import UserModelStat
from app.schemas.stats import ModelStatVO, UserModelStatVO, UserStatSummaryVO


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_model_stats(self, sort_by: str = "totalTokens") -> List[ModelStatVO]:
        result = await self.db.execute(
            select(Model).where(Model.is_delete == 0)
        )
        models = list(result.scalars().all())
        stats = [
            ModelStatVO(
                id=m.id,
                name=m.name,
                provider=m.provider,
                totalTokens=int(m.total_tokens or 0),
                totalCost=float(m.total_cost or 0),
                batchCallCount=int(m.batch_call_count or 0),
            )
            for m in models
        ]
        stats.sort(
            key=lambda x: x.model_dump(by_alias=True).get(sort_by, 0),
            reverse=True
        )
        return stats

    async def list_user_model_stats(self, user_id: int) -> List[UserModelStatVO]:
        result = await self.db.execute(
            select(UserModelStat).where(UserModelStat.user_id == user_id)
            .order_by(UserModelStat.total_cost.desc())
        )
        return [
            UserModelStatVO(
                modelName=s.model_name,
                callCount=int(s.call_count or 0),
                totalInputTokens=int(s.total_input_tokens or 0),
                totalOutputTokens=int(s.total_output_tokens or 0),
                totalCost=float(s.total_cost or 0),
                lastUsedAt=s.last_used_at.isoformat() if s.last_used_at else None,
            )
            for s in result.scalars().all()
        ]

    async def get_user_summary(self, user_id: int) -> UserStatSummaryVO:
        stats = await self.list_user_model_stats(user_id)
        total_calls = sum(s.call_count for s in stats)
        total_input = sum(s.total_input_tokens for s in stats)
        total_output = sum(s.total_output_tokens for s in stats)
        total_cost = sum(s.total_cost for s in stats)
        return UserStatSummaryVO(
            totalCalls=total_calls,
            totalInputTokens=total_input,
            totalOutputTokens=total_output,
            totalCost=total_cost,
            modelCount=len(stats),
        )
