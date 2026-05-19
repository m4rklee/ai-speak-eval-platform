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

    model_config = {"populate_by_name": True}


class ContentEvalJobVO(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    progress: int = 0
    total_files: int = Field(default=0, alias="totalFiles")
    error: Optional[str] = None
    summary: Optional[ContentEvalJobSummaryVO] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")
    result: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    progress_detail: Optional[ContentEvalProgressDetailVO] = Field(
        default=None, alias="progressDetail"
    )

    model_config = {"populate_by_name": True}


class ContentEvalJobListVO(BaseModel):
    jobs: list[ContentEvalJobVO] = Field(default_factory=list)
