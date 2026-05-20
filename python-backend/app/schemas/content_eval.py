from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ContentEvalHealthVO(BaseModel):
    question_dir_ok: bool = Field(default=False, alias="questionDirOk")
    question_dir_message: str = Field(default="", alias="questionDirMessage")
    question_count: int = Field(default=0, alias="questionCount")
    question_dir: str = Field(default="", alias="questionDir")
    judge_model: str = Field(default="", alias="judgeModel")
    max_files_per_job: int = Field(default=200, alias="maxFilesPerJob")

    model_config = {"populate_by_name": True}


class ContentEvalQuestionsVO(BaseModel):
    ids: list[str] = Field(default_factory=list)
    count: int = 0


class ContentEvalQuestionTextVO(BaseModel):
    question_id: str = Field(alias="questionId")
    question: str = ""

    model_config = {"populate_by_name": True}


class ContentEvalSingleResultVO(BaseModel):
    status: str = "ok"
    file_name: str = Field(alias="fileName")
    question_id: str = Field(default="", alias="questionId")
    question: str = ""
    answer: str = ""
    grammar_score: Optional[float] = Field(default=None, alias="grammarScore")
    theme_focus_score: Optional[float] = Field(default=None, alias="themeFocusScore")
    answer_clarity_score: Optional[float] = Field(default=None, alias="answerClarityScore")
    composite_score: Optional[float] = Field(default=None, alias="compositeScore")
    reason: Optional[str] = None
    dimensions: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class ContentEvalDimensionSummaryVO(BaseModel):
    dim_name_cn: str = Field(alias="dimNameCn")
    dim_name_en: str = Field(alias="dimNameEn")
    score: float = 0

    model_config = {"populate_by_name": True}


class ContentEvalJobSummaryVO(BaseModel):
    file_count: int = Field(default=0, alias="fileCount")
    ok_count: int = Field(default=0, alias="okCount")
    grammar_mean: Optional[float] = Field(default=None, alias="grammarMean")
    theme_focus_mean: Optional[float] = Field(default=None, alias="themeFocusMean")
    answer_clarity_mean: Optional[float] = Field(default=None, alias="answerClarityMean")
    composite_mean: Optional[float] = Field(default=None, alias="compositeMean")
    dimensions: list[ContentEvalDimensionSummaryVO] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ContentEvalProgressDetailVO(BaseModel):
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
    warning_line: Optional[str] = Field(default=None, alias="warningLine")

    model_config = {"populate_by_name": True}


class ContentEvalModelComparisonVO(BaseModel):
    model_name: str = Field(alias="modelName")
    file_count: int = Field(default=0, alias="fileCount")
    grammar_mean: Optional[float] = Field(default=None, alias="grammarMean")
    theme_focus_mean: Optional[float] = Field(default=None, alias="themeFocusMean")
    answer_clarity_mean: Optional[float] = Field(default=None, alias="answerClarityMean")
    composite_mean: Optional[float] = Field(default=None, alias="compositeMean")

    model_config = {"populate_by_name": True}


class ContentEvalModelResultVO(BaseModel):
    model_name: str = Field(alias="modelName")
    summary: Optional[ContentEvalJobSummaryVO] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")

    model_config = {"populate_by_name": True}


class ContentEvalJobVO(BaseModel):
    job_id: str = Field(alias="jobId")
    job_type: Optional[str] = Field(default=None, alias="jobType")
    status: str
    progress: int = 0
    total_files: int = Field(default=0, alias="totalFiles")
    model_count: Optional[int] = Field(default=None, alias="modelCount")
    error: Optional[str] = None
    summary: Optional[ContentEvalJobSummaryVO] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")
    models: Optional[list[ContentEvalModelResultVO]] = None
    comparison: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    progress_detail: Optional[ContentEvalProgressDetailVO] = Field(
        default=None, alias="progressDetail"
    )
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
    judge_model: Optional[str] = Field(default=None, alias="judgeModel")
    api_error_count: int = Field(default=0, alias="apiErrorCount")
    last_api_error: Optional[str] = Field(default=None, alias="lastApiError")
    last_api_error_at: Optional[str] = Field(default=None, alias="lastApiErrorAt")
    total_input_tokens: int = Field(default=0, alias="totalInputTokens")
    total_output_tokens: int = Field(default=0, alias="totalOutputTokens")
    estimated_cost_usd: Optional[float] = Field(default=None, alias="estimatedCostUsd")

    model_config = {"populate_by_name": True}


class ContentEvalJobListVO(BaseModel):
    jobs: list[ContentEvalJobVO] = Field(default_factory=list)
