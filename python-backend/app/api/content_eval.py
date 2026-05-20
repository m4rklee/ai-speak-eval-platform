"""内容评测 API（语法 / 主题聚焦 / 回复简洁清晰）。"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.common import BaseResponse
from app.schemas.eval_job_common import EvalJobDisplayNameUpdateVO
from app.schemas.content_eval import (
    ContentEvalHealthVO,
    ContentEvalJobListVO,
    ContentEvalJobVO,
    ContentEvalQuestionsVO,
    ContentEvalQuestionTextVO,
    ContentEvalSingleResultVO,
)
from app.services.content_eval_job_service import ContentEvalJobService
from app.services.user_service import UserService

router = APIRouter(prefix="/content-eval", tags=["内容评测"])


@router.get("/health", response_model=BaseResponse[ContentEvalHealthVO], summary="内容评测状态")
async def content_eval_health():
    data = ContentEvalJobService.health()
    return BaseResponse(
        code=0,
        data=ContentEvalHealthVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/questions",
    response_model=BaseResponse[ContentEvalQuestionsVO],
    summary="内置题目 ID 列表",
)
async def list_questions(q: Optional[str] = None):
    data = ContentEvalJobService.list_questions(q)
    return BaseResponse(
        code=0,
        data=ContentEvalQuestionsVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.get(
    "/questions/{question_id}",
    response_model=BaseResponse[ContentEvalQuestionTextVO],
    summary="获取题目文本",
)
async def get_question(question_id: str):
    data = ContentEvalJobService.get_question_text(question_id)
    return BaseResponse(
        code=0,
        data=ContentEvalQuestionTextVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.post(
    "/evaluate",
    response_model=BaseResponse[ContentEvalSingleResultVO],
    summary="单条内容评测",
)
async def evaluate_single(
    request: Request,
    question_id: Optional[str] = Form(default=None),
    answer: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await ContentEvalJobService.evaluate_single(
        user_id=user.id,
        question_id=question_id,
        answer_text=answer,
        file=file,
    )
    return BaseResponse(
        code=0,
        data=ContentEvalSingleResultVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )


@router.post("/jobs", response_model=BaseResponse[str], summary="创建批量内容评测任务")
async def create_job(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    files: list[UploadFile] = File(default=[]),
    archive: Optional[UploadFile] = File(default=None),
    display_name: Optional[str] = Form(default=None, alias="displayName"),
    eval_rounds: Optional[int] = Form(default=None, alias="evalRounds"),
    judge_model: Optional[str] = Form(default=None, alias="judgeModel"),
):
    user = await UserService.get_login_user(db, request)
    job_id = await ContentEvalJobService.create_job(
        user.id,
        files,
        archive,
        display_name=display_name,
        eval_rounds=eval_rounds,
        judge_model=judge_model,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.post(
    "/multi-model-jobs",
    response_model=BaseResponse[str],
    summary="创建多模型内容对比评测任务",
)
async def create_multi_model_job(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    form = await request.form()
    display_name = form.get("displayName")
    eval_rounds_raw = form.get("evalRounds")
    judge_model = form.get("judgeModel")
    eval_rounds = int(eval_rounds_raw) if eval_rounds_raw not in (None, "") else None
    job_id = await ContentEvalJobService.create_multi_model_job(
        user.id,
        form,
        display_name=str(display_name).strip() if display_name else None,
        eval_rounds=eval_rounds,
        judge_model=str(judge_model).strip() if judge_model else None,
    )
    return BaseResponse(code=0, data=job_id, message="ok")


@router.get(
    "/jobs",
    response_model=BaseResponse[ContentEvalJobListVO],
    summary="当前用户最近内容评测任务",
)
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    jobs = await ContentEvalJobService.list_jobs(user.id)
    vo = ContentEvalJobListVO(
        jobs=[ContentEvalJobVO.model_validate(j) for j in jobs],
    )
    return BaseResponse(
        code=0,
        data=vo.model_dump(by_alias=True),
        message="ok",
    )


@router.post(
    "/jobs/{job_id}/resume",
    response_model=BaseResponse[None],
    summary="续跑已中断的内容评测任务",
)
async def resume_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await ContentEvalJobService.resume_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/pause",
    response_model=BaseResponse[None],
    summary="暂停内容评测任务",
)
async def pause_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await ContentEvalJobService.pause_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.post(
    "/jobs/{job_id}/rerun",
    response_model=BaseResponse[None],
    summary="重跑内容评测任务",
)
async def rerun_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await ContentEvalJobService.rerun_job(user.id, job_id)
    return BaseResponse(code=0, data=None, message="ok")


@router.patch(
    "/jobs/{job_id}/display-name",
    response_model=BaseResponse[None],
    summary="更新任务显示名称",
)
async def update_display_name(
    job_id: str,
    body: EvalJobDisplayNameUpdateVO,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    await ContentEvalJobService.update_display_name(user.id, job_id, body.display_name)
    return BaseResponse(code=0, data=None, message="ok")


@router.get(
    "/jobs/{job_id}",
    response_model=BaseResponse[ContentEvalJobVO],
    summary="查询内容评测任务",
)
async def get_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    user = await UserService.get_login_user(db, request)
    data = await ContentEvalJobService.get_job(job_id, user.id)
    return BaseResponse(
        code=0,
        data=ContentEvalJobVO.model_validate(data).model_dump(by_alias=True),
        message="ok",
    )
