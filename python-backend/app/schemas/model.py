from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import json


class ModelListQuery(BaseModel):
    platform: Optional[str] = None
    input_modality: Optional[str] = Field(None, alias="inputModality")
    output_modality: Optional[str] = Field(None, alias="outputModality")
    model_type: Optional[str] = Field(None, alias="modelType")
    keyword: Optional[str] = None
    sort_by: str = Field(default="name", alias="sortBy")
    sort_order: str = Field(default="asc", alias="sortOrder", description="asc 或 desc")

    model_config = {"populate_by_name": True}


class ModelVO(BaseModel):
    id: str
    platform: str = "openrouter"
    platforms: Optional[List[str]] = Field(None, description="可用平台列表")
    alternate_ids: Optional[Dict[str, str]] = Field(
        None, alias="alternateIds", description="各平台复合模型 ID"
    )
    name: str
    description: Optional[str] = None
    provider: Optional[str] = None
    context_length: Optional[int] = Field(None, alias="contextLength")
    modality: Optional[str] = None
    input_modalities: List[str] = Field(default_factory=list, alias="inputModalities")
    output_modalities: List[str] = Field(default_factory=list, alias="outputModalities")
    input_price: Optional[Decimal] = Field(None, alias="inputPrice")
    output_price: Optional[Decimal] = Field(None, alias="outputPrice")
    released_at: Optional[str] = Field(None, alias="releasedAt")
    model_type: Optional[str] = Field(None, alias="modelType")
    recommended: int = 0
    is_china: int = Field(0, alias="isChina")
    total_tokens: Optional[int] = Field(None, alias="totalTokens")
    batch_call_count: Optional[int] = Field(None, alias="batchCallCount")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @field_validator("input_modalities", "output_modalities", mode="before")
    @classmethod
    def parse_modalities(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return [p.strip() for p in v.split(",") if p.strip()]
        return []
