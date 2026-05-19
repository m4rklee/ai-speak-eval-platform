from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BatchJobCreateRequest(BaseModel):
    scenario_id: str = Field(..., alias="scenarioId")
    models: List[str] = Field(..., min_length=1, max_length=8)
    concurrency: Optional[int] = Field(default=3, ge=1, le=10)
    output_modality: Optional[str] = Field("text", alias="outputModality")
    global_prompt: Optional[str] = Field(None, alias="globalPrompt")
    job_type: Optional[str] = Field("batch_audio", alias="jobType")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt")
    user_message_mode: Optional[str] = Field("text_plus_audio", alias="userMessageMode")
    eval_config: Optional[Dict[str, Any]] = Field(None, alias="evalConfig")
    auto_score: Optional[bool] = Field(True, alias="autoScore")
    sample_size: Optional[int] = Field(
        None,
        alias="sampleSize",
        ge=1,
        le=500,
        description="从场景中随机抽取 N 条用例参与本任务；不传则全量",
    )

    model_config = {"populate_by_name": True}


class BatchJobVO(BaseModel):
    id: str
    user_id: int = Field(..., alias="userId")
    scenario_id: str = Field(..., alias="scenarioId")
    scenario_name: Optional[str] = Field(None, alias="scenarioName")
    models: List[str]
    status: str
    total_tasks: int = Field(..., alias="totalTasks")
    completed_tasks: int = Field(..., alias="completedTasks")
    failed_tasks: int = Field(..., alias="failedTasks")
    concurrency: int
    output_modality: Optional[str] = Field("text", alias="outputModality")
    global_prompt: Optional[str] = Field(None, alias="globalPrompt")
    job_type: Optional[str] = Field(None, alias="jobType")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt")
    user_message_mode: Optional[str] = Field(None, alias="userMessageMode")
    eval_config: Optional[Dict[str, Any]] = Field(None, alias="evalConfig")
    error_summary: Optional[str] = Field(None, alias="errorSummary")
    started_at: Optional[str] = Field(None, alias="startedAt")
    finished_at: Optional[str] = Field(None, alias="finishedAt")
    create_time: Optional[str] = Field(None, alias="createTime")

    model_config = {"populate_by_name": True}


class BatchJobResultVO(BaseModel):
    id: str
    job_id: str = Field(..., alias="jobId")
    scenario_item_id: str = Field(..., alias="scenarioItemId")
    model_name: str = Field(..., alias="modelName")
    prompt: str
    expected_answer: str = Field(..., alias="expectedAnswer")
    output_content: Optional[str] = Field(None, alias="outputContent")
    output_audio: Optional[str] = Field(None, alias="outputAudio")
    output_modality: Optional[str] = Field(None, alias="outputModality")
    status: str
    error_message: Optional[str] = Field(None, alias="errorMessage")
    response_time_ms: Optional[int] = Field(None, alias="responseTimeMs")
    input_tokens: Optional[int] = Field(None, alias="inputTokens")
    output_tokens: Optional[int] = Field(None, alias="outputTokens")
    cost: Optional[float] = None
    score: Optional[float] = None
    eval_score: Optional[float] = Field(None, alias="evalScore")
    eval_detail: Optional[str] = Field(None, alias="evalDetail")

    model_config = {"populate_by_name": True}


class BatchJobListQuery(BaseModel):
    current: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, alias="pageSize", ge=1, le=50)

    model_config = {"populate_by_name": True}


class BatchResultQuery(BaseModel):
    current: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, alias="pageSize", ge=1, le=500)
    model_name: Optional[str] = Field(None, alias="modelName")
    status: Optional[str] = None

    model_config = {"populate_by_name": True}


class ProgressEvent(BaseModel):
    type: str
    job_id: str = Field(..., alias="jobId")
    completed_tasks: int = Field(..., alias="completedTasks")
    total_tasks: int = Field(..., alias="totalTasks")
    failed_tasks: int = Field(..., alias="failedTasks")
    current_model: Optional[str] = Field(None, alias="currentModel")
    current_item_index: Optional[int] = Field(None, alias="currentItemIndex")
    status: str

    model_config = {"populate_by_name": True}
