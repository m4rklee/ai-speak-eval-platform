from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ScenarioItemImportDTO(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    expected_answer: str = Field(default="-", alias="expectedAnswer", max_length=20000)
    category: Optional[str] = Field(None, max_length=100)
    audio_file_name: Optional[str] = Field(None, alias="audioFileName")
    audio_data: Optional[str] = Field(None, alias="audioData")
    audio_format: Optional[str] = Field(None, alias="audioFormat")
    input_type: Optional[str] = Field("text", alias="inputType")
    model_output: Optional[str] = Field(None, alias="modelOutput", max_length=50000)

    model_config = {"populate_by_name": True}

    @field_validator("prompt", mode="before")
    @classmethod
    def normalize_prompt(cls, v: object) -> str:
        text = (v or "").strip() if isinstance(v, str) else str(v or "").strip()
        return text or "请根据音频内容作答"

    @field_validator("expected_answer", mode="before")
    @classmethod
    def normalize_expected_answer(cls, v: object) -> str:
        text = (v or "").strip() if isinstance(v, str) else str(v or "").strip()
        return text or "-"


class ScenarioAddRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)


class ScenarioUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)


class ScenarioItemUpdateRequest(BaseModel):
    prompt: Optional[str] = Field(None, min_length=1, max_length=10000)
    expected_answer: Optional[str] = Field(None, alias="expectedAnswer", min_length=1, max_length=20000)
    category: Optional[str] = Field(None, max_length=100)
    sort_order: Optional[int] = Field(None, alias="sortOrder", ge=0)

    model_config = {"populate_by_name": True}


class ScenarioItemVO(BaseModel):
    id: str
    scenario_id: str = Field(..., alias="scenarioId")
    prompt: str
    expected_answer: str = Field(..., alias="expectedAnswer")
    category: Optional[str] = None
    input_type: Optional[str] = Field("text", alias="inputType")
    audio_file_name: Optional[str] = Field(None, alias="audioFileName")
    audio_format: Optional[str] = Field(None, alias="audioFormat")
    sort_order: int = Field(..., alias="sortOrder")
    model_output: Optional[str] = Field(None, alias="modelOutput")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ScenarioVO(BaseModel):
    id: str
    user_id: Optional[int] = Field(None, alias="userId")
    name: str
    description: Optional[str] = None
    source_type: str = Field(..., alias="sourceType")
    category: Optional[str] = None
    item_count: int = Field(..., alias="itemCount")
    create_time: Optional[str] = Field(None, alias="createTime")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ScenarioDetailVO(ScenarioVO):
    items: List[ScenarioItemVO] = Field(default_factory=list)


class ScenarioImportRequest(BaseModel):
    items: List[ScenarioItemImportDTO] = Field(..., min_length=1, max_length=500)


class PageQueryRequest(BaseModel):
    current: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, alias="pageSize", ge=1, le=100)

    model_config = {"populate_by_name": True}
