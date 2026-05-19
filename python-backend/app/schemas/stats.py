from typing import Optional

from pydantic import BaseModel, Field


class ModelStatVO(BaseModel):
    id: str
    name: str
    provider: Optional[str] = None
    total_tokens: int = Field(..., alias="totalTokens")
    total_cost: float = Field(..., alias="totalCost")
    batch_call_count: int = Field(..., alias="batchCallCount")

    model_config = {"populate_by_name": True}


class UserModelStatVO(BaseModel):
    model_name: str = Field(..., alias="modelName")
    call_count: int = Field(..., alias="callCount")
    total_input_tokens: int = Field(..., alias="totalInputTokens")
    total_output_tokens: int = Field(..., alias="totalOutputTokens")
    total_cost: float = Field(..., alias="totalCost")
    last_used_at: Optional[str] = Field(None, alias="lastUsedAt")

    model_config = {"populate_by_name": True}


class UserStatSummaryVO(BaseModel):
    total_calls: int = Field(..., alias="totalCalls")
    total_input_tokens: int = Field(..., alias="totalInputTokens")
    total_output_tokens: int = Field(..., alias="totalOutputTokens")
    total_cost: float = Field(..., alias="totalCost")
    model_count: int = Field(..., alias="modelCount")

    model_config = {"populate_by_name": True}
