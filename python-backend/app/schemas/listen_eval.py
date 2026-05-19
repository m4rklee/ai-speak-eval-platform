from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ListenEvalHealthVO(BaseModel):
    package_dir_ok: bool = Field(default=False, alias="packageDirOk")
    package_dir: str = Field(default="", alias="packageDir")
    benchmark_ok: bool = Field(default=False, alias="benchmarkOk")
    benchmark_path: str = Field(default="", alias="benchmarkPath")
    question_count: int = Field(default=0, alias="questionCount")
    audio_dir_ok: bool = Field(default=False, alias="audioDirOk")
    audio_dir: str = Field(default="", alias="audioDir")
    audio_file_count: int = Field(default=0, alias="audioFileCount")
    openrouter_configured: bool = Field(default=False, alias="openrouterConfigured")
    aihubmix_configured: bool = Field(default=False, alias="aihubmixConfigured")
    api_configured: bool = Field(default=False, alias="apiConfigured")
    ready: bool = False
    message: str = ""
    max_samples_per_job: int = Field(default=2201, alias="maxSamplesPerJob")

    model_config = {"populate_by_name": True}


class ListenEvalJobCreateVO(BaseModel):
    model: str = Field(..., min_length=1)
    sample_mode: Literal["all", "random"] = Field(alias="sampleMode")
    sample_count: int = Field(default=0, alias="sampleCount")
    seed: Optional[int] = None
    request_interval: Optional[float] = Field(default=None, alias="requestInterval")
    workers: Optional[int] = None

    model_config = {"populate_by_name": True}


class ListenEvalProgressDetailVO(BaseModel):
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


class ListenEvalJobVO(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    progress: int = 0
    total_samples: int = Field(default=0, alias="totalSamples")
    model: str = ""
    sample_mode: str = Field(default="", alias="sampleMode")
    error: Optional[str] = None
    summary: Optional[dict[str, Any]] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    progress_detail: Optional[ListenEvalProgressDetailVO] = Field(
        default=None, alias="progressDetail"
    )

    model_config = {"populate_by_name": True}


class ListenEvalJobListVO(BaseModel):
    jobs: list[ListenEvalJobVO] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
