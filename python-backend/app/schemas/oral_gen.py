from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OralGenHealthVO(BaseModel):
    questionwav_dir_ok: bool = Field(default=False, alias="questionwavDirOk")
    questionwav_dir: str = Field(default="", alias="questionwavDir")
    wav_count: int = Field(default=0, alias="wavCount")
    openrouter_configured: bool = Field(default=False, alias="openrouterConfigured")
    aihubmix_configured: bool = Field(default=False, alias="aihubmixConfigured")
    api_configured: bool = Field(default=False, alias="apiConfigured")
    ready: bool = False
    message: str = ""
    max_samples_per_job: int = Field(default=200, alias="maxSamplesPerJob")
    system_prompt: str = Field(default="", alias="systemPrompt")

    model_config = {"populate_by_name": True}


class OralGenJobCreateVO(BaseModel):
    model: str = Field(..., min_length=1)
    source: Literal["builtin"] = "builtin"
    sample_mode: Literal["all", "random"] = Field(alias="sampleMode")
    sample_count: int = Field(default=0, alias="sampleCount")
    seed: Optional[int] = None
    request_interval: Optional[float] = Field(default=None, alias="requestInterval")

    model_config = {"populate_by_name": True}


class OralGenProgressDetailVO(BaseModel):
    phase: Optional[str] = None
    phase_label: str = Field(default="", alias="phaseLabel")
    current: int = 0
    total: int = 0
    elapsed_sec: Optional[float] = Field(default=None, alias="elapsedSec")
    eta_sec: Optional[float] = Field(default=None, alias="etaSec")
    elapsed_text: str = Field(default="", alias="elapsedText")
    eta_text: str = Field(default="", alias="etaText")
    rate_per_sec: Optional[float] = Field(default=None, alias="ratePerSec")
    message: str = ""
    tqdm_line: str = Field(default="", alias="tqdmLine")

    model_config = {"populate_by_name": True}


class OralGenResultRowVO(BaseModel):
    stem: str = ""
    text: str = ""
    has_audio: bool = Field(default=False, alias="hasAudio")
    error: Optional[str] = None
    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")

    model_config = {"populate_by_name": True}


class OralGenJobSummaryVO(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0

    model_config = {"populate_by_name": True}


class OralGenJobVO(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    progress: int = 0
    total_samples: int = Field(default=0, alias="totalSamples")
    model: str = ""
    source: str = ""
    sample_mode: str = Field(default="", alias="sampleMode")
    error: Optional[str] = None
    summary: Optional[OralGenJobSummaryVO] = None
    rows: Optional[list[OralGenResultRowVO]] = None
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    progress_detail: Optional[OralGenProgressDetailVO] = Field(
        default=None, alias="progressDetail"
    )

    model_config = {"populate_by_name": True}


class OralGenJobListVO(BaseModel):
    jobs: list[OralGenJobVO] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
