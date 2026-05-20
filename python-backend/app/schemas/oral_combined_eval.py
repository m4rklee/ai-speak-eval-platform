from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.content_eval import ContentEvalProgressDetailVO


class OralCombinedHealthVO(BaseModel):
    paths_ok: bool = Field(default=False, alias="pathsOk")
    paths_message: str = Field(default="", alias="pathsMessage")
    daemon_running: bool = Field(default=False, alias="daemonRunning")
    daemon_ready: bool = Field(default=False, alias="daemonReady")
    question_dir_ok: bool = Field(default=False, alias="questionDirOk")
    question_dir_message: str = Field(default="", alias="questionDirMessage")
    question_count: int = Field(default=0, alias="questionCount")
    judge_model: str = Field(default="", alias="judgeModel")
    max_files_per_job: int = Field(default=200, alias="maxFilesPerJob")
    engine: str = "daemon"
    oral_gen_ready: bool = Field(default=False, alias="oralGenReady")
    questionwav_count: int = Field(default=0, alias="questionwavCount")
    oral_gen_message: str = Field(default="", alias="oralGenMessage")

    model_config = {"populate_by_name": True}


class OralCombinedGenRowVO(BaseModel):
    stem: str = ""
    text: str = ""
    has_audio: bool = Field(default=False, alias="hasAudio")
    error: Optional[str] = None
    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")

    model_config = {"populate_by_name": True}


class OralCombinedPipelineCreateVO(BaseModel):
    model: str
    source: str = "builtin"
    sample_mode: str = Field(default="random", alias="sampleMode")
    sample_count: int = Field(default=2, alias="sampleCount")
    seed: Optional[int] = None
    request_interval: Optional[float] = Field(default=None, alias="requestInterval")
    auto_start_eval: bool = Field(default=True, alias="autoStartEval")

    model_config = {"populate_by_name": True}


class OralCombinedFromOralGenVO(BaseModel):
    auto_start_eval: bool = Field(default=True, alias="autoStartEval")

    model_config = {"populate_by_name": True}


class OralCombinedSpeechSideVO(BaseModel):
    status: str = "ok"
    accuracy: Optional[float] = None
    fluency: Optional[float] = None
    naturalness: Optional[float] = None
    apg_mos: Optional[dict[str, Any]] = Field(default=None, alias="apgMos")
    apg_mos_errors: Optional[dict[str, str]] = Field(default=None, alias="apgMosErrors")
    transcript_s: str = Field(default="", alias="transcriptS")
    transcript_w: str = Field(default="", alias="transcriptW")
    reason: Optional[str] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class OralCombinedContentSideVO(BaseModel):
    status: str = "ok"
    question_id: str = Field(default="", alias="questionId")
    question: str = ""
    grammar_score: Optional[float] = Field(default=None, alias="grammarScore")
    theme_focus_score: Optional[float] = Field(default=None, alias="themeFocusScore")
    answer_clarity_score: Optional[float] = Field(default=None, alias="answerClarityScore")
    composite_score: Optional[float] = Field(default=None, alias="compositeScore")
    reason: Optional[str] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class OralCombinedPerFileVO(BaseModel):
    stem: str = ""
    wav_name: str = Field(default="", alias="wavName")
    txt_name: str = Field(default="", alias="txtName")
    status: str = "ok"
    speech: Optional[OralCombinedSpeechSideVO] = None
    content: Optional[OralCombinedContentSideVO] = None

    model_config = {"populate_by_name": True}


class OralCombinedGenSummaryVO(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0
    eval_skipped: int = Field(default=0, alias="evalSkipped")

    model_config = {"populate_by_name": True}


class OralCombinedSummaryVO(BaseModel):
    pair_count: int = Field(default=0, alias="pairCount")
    ok_count: int = Field(default=0, alias="okCount")
    partial_count: int = Field(default=0, alias="partialCount")
    error_count: int = Field(default=0, alias="errorCount")
    gen_summary: Optional[OralCombinedGenSummaryVO] = Field(default=None, alias="genSummary")
    accuracy_mean: Optional[float] = Field(default=None, alias="accuracyMean")
    fluency_mean: Optional[float] = Field(default=None, alias="fluencyMean")
    naturalness_mean: Optional[float] = Field(default=None, alias="naturalnessMean")
    apg_mos_bvcc_mean: Optional[float] = Field(default=None, alias="apgMosBvccMean")
    apg_mos_somos_mean: Optional[float] = Field(default=None, alias="apgMosSomosMean")
    grammar_mean: Optional[float] = Field(default=None, alias="grammarMean")
    theme_focus_mean: Optional[float] = Field(default=None, alias="themeFocusMean")
    answer_clarity_mean: Optional[float] = Field(default=None, alias="answerClarityMean")
    composite_mean: Optional[float] = Field(default=None, alias="compositeMean")

    model_config = {"populate_by_name": True}


class OralCombinedJobVO(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    progress: int = 0
    total_files: int = Field(default=0, alias="totalFiles")
    error: Optional[str] = None
    summary: Optional[OralCombinedSummaryVO] = None
    per_file: Optional[list[dict[str, Any]]] = Field(default=None, alias="perFile")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    progress_detail: Optional[ContentEvalProgressDetailVO] = Field(
        default=None, alias="progressDetail"
    )
    audio_available: bool = Field(default=False, alias="audioAvailable")
    pipeline_mode: bool = Field(default=False, alias="pipelineMode")
    model: Optional[str] = None
    gen_rows: Optional[list[OralCombinedGenRowVO]] = Field(default=None, alias="genRows")
    gen_summary: Optional[OralCombinedGenSummaryVO] = Field(default=None, alias="genSummary")
    auto_start_eval: Optional[bool] = Field(default=None, alias="autoStartEval")

    model_config = {"populate_by_name": True}


class OralCombinedJobListVO(BaseModel):
    jobs: list[OralCombinedJobVO] = Field(default_factory=list)
