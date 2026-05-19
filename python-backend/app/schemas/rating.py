"""
用户评分请求模型
"""
from typing import Optional

from pydantic import BaseModel, Field


class RatingRequest(BaseModel):
    """用户评分请求"""
    conversation_id: str = Field(..., alias="conversationId")
    message_index: int = Field(..., ge=0, alias="messageIndex")
    rating_type: str = Field(..., alias="ratingType")
    winner_model: Optional[str] = Field(None, alias="winnerModel")
    loser_model: Optional[str] = Field(None, alias="loserModel")

    model_config = {"populate_by_name": True}
