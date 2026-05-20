from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class UnifiedEvalHealthVO(BaseModel):
    unified_eval_enabled: bool = Field(default=False, alias="unifiedEvalEnabled")
    use_daemon: bool = Field(default=False, alias="useDaemon")
    paths_ok: bool = Field(default=False, alias="pathsOk")
    paths_message: str = Field(default="", alias="pathsMessage")
    daemon_running: bool = Field(default=False, alias="daemonRunning")
    daemon_ready: bool = Field(default=False, alias="daemonReady")
    multipa_port: int = Field(default=0, alias="multipaPort")
    apg_port: int = Field(default=0, alias="apgPort")
    engine: str = "daemon"

    model_config = {"populate_by_name": True}


class UnifiedEvalFileResultVO(BaseModel):
    wavname: str
    status: str = "ok"
    accuracy: Optional[float] = None
    fluency: Optional[float] = None
    naturalness: Optional[float] = None
    apg_mos: Optional[dict[str, Any]] = None
    apg_mos_errors: Optional[dict[str, str]] = None
    transcript_s: str = Field(default="", alias="transcriptS")
    transcript_w: str = Field(default="", alias="transcriptW")
    reason: Optional[str] = None

    model_config = {"populate_by_name": True}


class UnifiedEvalSingleResultVO(BaseModel):
    status: str
    file_name: str = Field(alias="fileName")
    accuracy: Optional[float] = None
    fluency: Optional[float] = None
    naturalness: Optional[float] = None
    apg_mos: Optional[dict[str, Any]] = Field(default=None, alias="apgMos")
    apg_mos_errors: Optional[dict[str, str]] = Field(default=None, alias="apgMosErrors")
    transcripts: Optional[dict[str, str]] = None
    reason: Optional[str] = None
    raw: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class UnifiedEvalJobSummaryVO(BaseModel):
    multipa: Optional[dict[str, float]] = None
    apg_mos_bvcc_mean: Optional[float] = Field(default=None, alias="apgMosBvccMean")
    apg_mos_somos_mean: Optional[float] = Field(default=None, alias="apgMosSomosMean")
    file_count: int = Field(default=0, alias="fileCount")

    model_config = {"populate_by_name": True}


class UnifiedEvalModelComparisonVO(BaseModel):
    model_name: str = Field(alias="modelName")
    file_count: int = Field(default=0, alias="fileCount")
    accuracy_mean: Optional[float] = Field(default=None, alias="accuracyMean")
    fluency_mean: Optional[float] = Field(default=None, alias="fluencyMean")
    naturalness_mean: Optional[float] = Field(default=None, alias="naturalnessMean")
    apg_mos_bvcc_mean: Optional[float] = Field(default=None, alias="apgMosBvccMean")
    apg_mos_somos_mean: Optional[float] = Field(default=None, alias="apgMosSomosMean")

    model_config = {"populate_by_name": True}


class UnifiedEvalModelResultVO(BaseModel):
    model_name: str = Field(alias="modelName")
    summary: Optional[UnifiedEvalJobSummaryVO] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")

    model_config = {"populate_by_name": True}


class UnifiedEvalComparisonVO(BaseModel):
    by_model: list[UnifiedEvalModelComparisonVO] = Field(default_factory=list, alias="byModel")

    model_config = {"populate_by_name": True}


class UnifiedEvalProgressDetailVO(BaseModel):
    phase: Optional[str] = None
    phase_label: str = Field(default="", alias="phaseLabel")
    current: int = 0
    total: int = 0
    multipa_current: int = Field(default=0, alias="multipaCurrent")
    multipa_total: int = Field(default=0, alias="multipaTotal")
    apg_current: int = Field(default=0, alias="apgCurrent")
    apg_total: int = Field(default=0, alias="apgTotal")
    multipa_done: bool = Field(default=False, alias="multipaDone")
    apg_done: bool = Field(default=False, alias="apgDone")
    elapsed_sec: Optional[float] = Field(default=None, alias="elapsedSec")
    eta_sec: Optional[float] = Field(default=None, alias="etaSec")
    elapsed_text: str = Field(default="", alias="elapsedText")
    eta_text: str = Field(default="", alias="etaText")
    rate_per_sec: Optional[float] = Field(default=None, alias="ratePerSec")
    message: str = ""
    tqdm_line: str = Field(default="", alias="tqdmLine")
    warning_line: Optional[str] = Field(default=None, alias="warningLine")

    model_config = {"populate_by_name": True}


class UnifiedEvalJobVO(BaseModel):
    job_id: str = Field(alias="jobId")
    job_type: str = Field(default="single", alias="jobType")
    status: str
    progress: int = 0
    total_files: int = Field(default=0, alias="totalFiles")
    model_count: int = Field(default=0, alias="modelCount")
    error: Optional[str] = None
    summary: Optional[UnifiedEvalJobSummaryVO] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")
    models: Optional[list[UnifiedEvalModelResultVO]] = None
    comparison: Optional[UnifiedEvalComparisonVO] = None
    result: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    progress_detail: Optional[UnifiedEvalProgressDetailVO] = Field(
        default=None, alias="progressDetail"
    )
    audio_available: bool = Field(default=False, alias="audioAvailable")
    completed_count: Optional[int] = Field(default=None, alias="completedCount")
    total_count: Optional[int] = Field(default=None, alias="totalCount")
    can_resume: Optional[bool] = Field(default=None, alias="canResume")
    interrupted_at: Optional[str] = Field(default=None, alias="interruptedAt")
    paused_at: Optional[str] = Field(default=None, alias="pausedAt")
    can_pause: Optional[bool] = Field(default=None, alias="canPause")
    can_rerun: Optional[bool] = Field(default=None, alias="canRerun")
    has_checkpoint: Optional[bool] = Field(default=None, alias="hasCheckpoint")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    eval_rounds: Optional[int] = Field(default=None, alias="evalRounds")
    api_error_count: int = Field(default=0, alias="apiErrorCount")
    last_api_error: Optional[str] = Field(default=None, alias="lastApiError")
    last_api_error_at: Optional[str] = Field(default=None, alias="lastApiErrorAt")
    total_input_tokens: int = Field(default=0, alias="totalInputTokens")
    total_output_tokens: int = Field(default=0, alias="totalOutputTokens")
    estimated_cost_usd: Optional[float] = Field(default=None, alias="estimatedCostUsd")

    model_config = {"populate_by_name": True}


class UnifiedEvalJobListVO(BaseModel):
    jobs: list[UnifiedEvalJobVO] = Field(default_factory=list)
