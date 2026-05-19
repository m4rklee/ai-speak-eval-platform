import asyncio
import base64
import random
import io
import json
import time
import uuid
import zipfile
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.db.session import AsyncSessionLocal
from app.models.batch_job import BatchJob
from app.models.batch_job_result import BatchJobResult
from app.models.model import Model
from app.models.scenario import Scenario
from app.models.scenario_item import ScenarioItem
from app.models.user_model_stat import UserModelStat
from app.providers.registry import get_provider
from app.schemas.batch import BatchJobCreateRequest, BatchJobVO, BatchJobResultVO
from app.schemas.conversation import AudioInput
from app.services.conversation_service import ConversationService
from app.services.oral_eval.oral_scoring_service import OralScoringService
from app.services.progress_publisher import ProgressPublisher
from app.utils.oral_practice import (
    build_oral_practice_messages,
    default_eval_config,
    default_system_prompt,
)
from app.utils.cost_calculator import CostCalculator
from app.utils.model_id import normalize_model_id, split_model_id, vendor_model_id
from app.utils.rate_limiter import RateLimitType, check_rate_limit


class BatchJobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _sample_items(
        items: List[ScenarioItem],
        sample_size: Optional[int],
        eval_config: Optional[dict[str, Any]],
    ) -> tuple[List[ScenarioItem], Optional[dict[str, Any]]]:
        if not sample_size or sample_size >= len(items):
            return items, eval_config
        picked = random.sample(items, sample_size)
        cfg = dict(eval_config) if isinstance(eval_config, dict) else {}
        cfg["sampleItemIds"] = [it.id for it in picked]
        cfg["sampleSize"] = sample_size
        cfg["scenarioItemCount"] = len(items)
        return picked, cfg

    @staticmethod
    def _filter_items_by_job_config(
        items: List[ScenarioItem],
        eval_config: Any,
    ) -> List[ScenarioItem]:
        if not isinstance(eval_config, dict):
            return items
        ids = eval_config.get("sampleItemIds")
        if not ids:
            return items
        id_set = set(ids)
        filtered = [it for it in items if it.id in id_set]
        return filtered if filtered else items

    async def create_job(self, request: BatchJobCreateRequest, user_id: int) -> str:
        await check_rate_limit(
            get_redis(), None,
            RateLimitType.USER, 5, 600,
            message="批量任务创建过于频繁，请稍后再试",
            identifier=user_id
        )

        result = await self.db.execute(
            select(Scenario).where(
                Scenario.id == request.scenario_id,
                Scenario.is_delete == 0
            )
        )
        scenario = result.scalar_one_or_none()
        if not scenario:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "场景不存在")
        if scenario.source_type != 'system' and scenario.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限使用该场景")

        items_result = await self.db.execute(
            select(ScenarioItem).where(
                ScenarioItem.scenario_id == request.scenario_id,
                ScenarioItem.is_delete == 0
            )
        )
        items = list(items_result.scalars().all())
        if not items:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "场景中没有测试用例")

        eval_config = request.eval_config
        items, eval_config = self._sample_items(items, request.sample_size, eval_config)

        job_type = request.job_type or 'batch_audio'
        models = [m.strip() for m in request.models if m and m.strip()]
        if job_type == 'score_only':
            models = [normalize_model_id(m) for m in models] if models else ['imported']
            missing = [it for it in items if not (getattr(it, 'model_output', None) or '').strip()]
            if missing:
                raise BusinessException(
                    ErrorCode.PARAMS_ERROR,
                    f"批量文本评分需要每条用例有待评文本（modelOutput），缺少 {len(missing)} 条",
                )
        else:
            models = [normalize_model_id(m) for m in models]
            if not models:
                raise BusinessException(ErrorCode.PARAMS_ERROR, "请选择至少一个模型")
        if len(models) > 8:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "最多支持8个模型")

        job_id = str(uuid.uuid4())
        total_tasks = len(items) * len(models)
        output_modality = request.output_modality or 'text'
        user_message_mode = request.user_message_mode or 'text_plus_audio'
        system_prompt = request.system_prompt

        if job_type == 'oral_practice':
            output_modality = request.output_modality or 'text+audio'
            user_message_mode = request.user_message_mode or 'audio_only'
            system_prompt = system_prompt or default_system_prompt()
            eval_config = eval_config or default_eval_config()
        elif job_type == 'score_only':
            output_modality = 'text'
            eval_config = eval_config or default_eval_config()

        job = BatchJob(
            id=job_id,
            user_id=user_id,
            scenario_id=request.scenario_id,
            models=models,
            status='pending',
            total_tasks=total_tasks,
            completed_tasks=0,
            failed_tasks=0,
            concurrency=request.concurrency or 3,
            output_modality=output_modality,
            global_prompt=request.global_prompt,
            job_type=job_type,
            system_prompt=system_prompt,
            user_message_mode=user_message_mode,
            eval_config=eval_config,
            is_delete=0
        )
        self.db.add(job)
        await self.db.commit()

        payload = await ProgressPublisher.build_progress_payload(
            job_id, 'pending', 0, total_tasks, 0, event_type='snapshot'
        )
        await ProgressPublisher.publish(job_id, payload)

        asyncio.create_task(self._run_job(job_id))
        return job_id

    async def cancel_job(self, job_id: str, user_id: int) -> bool:
        job = await self._get_user_job(job_id, user_id)
        if job.status in ('completed', 'failed', 'cancelled'):
            return True
        job.status = 'cancelled'
        job.finished_at = datetime.now()
        await self.db.commit()
        payload = await ProgressPublisher.build_progress_payload(
            job_id, 'cancelled', job.completed_tasks, job.total_tasks, job.failed_tasks,
            event_type='cancelled'
        )
        await ProgressPublisher.publish(job_id, payload)
        return True

    async def get_job(self, job_id: str, user_id: int) -> BatchJobVO:
        job = await self._get_user_job(job_id, user_id)
        scenario = await self.db.get(Scenario, job.scenario_id)
        return self._to_job_vo(job, scenario.name if scenario else None)

    async def list_jobs(self, user_id: int, current: int, page_size: int) -> Dict[str, Any]:
        query = select(BatchJob).where(BatchJob.user_id == user_id, BatchJob.is_delete == 0)
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        offset = (current - 1) * page_size
        result = await self.db.execute(
            query.order_by(BatchJob.create_time.desc()).offset(offset).limit(page_size)
        )
        jobs = result.scalars().all()
        records = []
        for job in jobs:
            scenario = await self.db.get(Scenario, job.scenario_id)
            records.append(
                self._to_job_vo(job, scenario.name if scenario else None).model_dump(by_alias=True)
            )
        return {"records": records, "total": total, "current": current, "pageSize": page_size}

    async def list_results(
        self,
        job_id: str,
        user_id: int,
        current: int,
        page_size: int,
        model_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        await self._get_user_job(job_id, user_id)
        query = select(BatchJobResult).where(
            BatchJobResult.job_id == job_id,
            BatchJobResult.is_delete == 0
        )
        if model_name:
            query = query.where(BatchJobResult.model_name == model_name)
        if status:
            query = query.where(BatchJobResult.status == status)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        offset = (current - 1) * page_size
        result = await self.db.execute(
            query.order_by(BatchJobResult.create_time.asc()).offset(offset).limit(page_size)
        )
        records = [
            self._to_result_vo(r).model_dump(by_alias=True)
            for r in result.scalars().all()
        ]
        return {"records": records, "total": total, "current": current, "pageSize": page_size}

    async def _run_job(self, job_id: str) -> None:
        async with AsyncSessionLocal() as db:
            service = BatchJobService(db)
            await service._execute_job(job_id)

    async def _execute_job(self, job_id: str) -> None:
        job = await self.db.get(BatchJob, job_id)
        if not job:
            return

        job.status = 'running'
        job.started_at = datetime.now()
        await self.db.commit()

        items_result = await self.db.execute(
            select(ScenarioItem).where(
                ScenarioItem.scenario_id == job.scenario_id,
                ScenarioItem.is_delete == 0
            ).order_by(ScenarioItem.sort_order.asc())
        )
        items = list(items_result.scalars().all())
        items = self._filter_items_by_job_config(items, getattr(job, 'eval_config', None))
        models: List[str] = job.models if isinstance(job.models, list) else []
        job_type = getattr(job, 'job_type', None) or 'batch_audio'

        semaphore = asyncio.Semaphore(job.concurrency or 3)
        tasks = []
        for item_index, item in enumerate(items):
            for model_name in models:
                tasks.append((item_index, item, model_name))

        async def run_one(item_index: int, item: ScenarioItem, model_name: str) -> None:
            async with semaphore:
                if job_type == 'score_only':
                    await self._process_score_only_task(job_id, job.user_id, item_index, item, model_name)
                else:
                    await self._process_task(job_id, job.user_id, item_index, item, model_name)

        await asyncio.gather(*[run_one(i, item, m) for i, item, m in tasks])

        job = await self.db.get(BatchJob, job_id)
        if not job:
            return
        if job.status == 'cancelled':
            event_type = 'cancelled'
        elif job.failed_tasks >= job.total_tasks:
            job.status = 'failed'
            event_type = 'failed'
        else:
            job.status = 'completed'
            event_type = 'completed'
        await self.db.commit()

        payload = await ProgressPublisher.build_progress_payload(
            job_id, job.status, job.completed_tasks, job.total_tasks, job.failed_tasks,
            event_type=event_type, phase='generate',
        )
        await ProgressPublisher.publish(job_id, payload)

        if event_type == 'completed' and self._should_auto_score(job):
            await self._run_scoring_phase(job_id, job.user_id)

        job = await self.db.get(BatchJob, job_id)
        if job and job.status != 'cancelled':
            job.finished_at = datetime.now()
            await self.db.commit()
            payload = await ProgressPublisher.build_progress_payload(
                job_id, job.status, job.completed_tasks, job.total_tasks, job.failed_tasks,
                event_type='completed' if job.status == 'completed' else job.status,
                phase='done',
            )
            await ProgressPublisher.publish(job_id, payload)

    async def _process_task(
        self,
        job_id: str,
        user_id: int,
        item_index: int,
        item: ScenarioItem,
        model_name: str
    ) -> None:
        async with AsyncSessionLocal() as db:
            job = await db.get(BatchJob, job_id)
            if not job or job.status == 'cancelled':
                return

        start_time = time.time()
        output_content = ""
        output_audio_json = None
        output_modality_actual = None
        error_message = None
        status = 'success'
        input_tokens = 0
        output_tokens = 0
        cost = Decimal('0')

        async with AsyncSessionLocal() as db:
            job_cfg = await db.get(BatchJob, job_id)
            global_prompt = job_cfg.global_prompt if job_cfg else None
            output_modality = (job_cfg.output_modality if job_cfg else None) or 'text'
            job_type = getattr(job_cfg, 'job_type', None) or 'batch_audio'
            user_message_mode = getattr(job_cfg, 'user_message_mode', None) or 'text_plus_audio'
            system_prompt = getattr(job_cfg, 'system_prompt', None)

        try:
            model_id = normalize_model_id(model_name)
            platform, _ = split_model_id(model_id)
            vendor_id = vendor_model_id(model_id)
            prompt_text = item.prompt
            if global_prompt:
                prompt_text = f"{global_prompt.strip()}\n\n{item.prompt}".strip()

            audio_inputs = None
            if item.audio_data:
                audio_inputs = [AudioInput(
                    data=item.audio_data,
                    format=item.audio_format or "wav",
                    name=item.audio_file_name,
                )]
            use_oral = job_type == 'oral_practice' or user_message_mode == 'audio_only'
            if use_oral and audio_inputs:
                messages = build_oral_practice_messages(
                    audio_inputs,
                    system_prompt=system_prompt,
                    user_message_mode=user_message_mode,
                    item_prompt=prompt_text if user_message_mode != 'audio_only' else None,
                )
            else:
                async with AsyncSessionLocal() as msg_db:
                    conv = ConversationService(msg_db)
                    messages = conv._build_messages(prompt_text, None, None, audio_inputs, None)
            require_audio = output_modality in ('audio', 'text+audio')
            api_timeout = 300.0 if (require_audio or audio_inputs) else 120.0
            provider = get_provider(platform)
            result = await provider.chat_completion(
                vendor_id,
                messages,
                require_audio_output=require_audio,
                max_tokens=4000,
                timeout=api_timeout,
            )
            output_content = result.text or ""
            input_tokens = result.input_tokens
            output_tokens = result.output_tokens
            if result.audio_data:
                output_audio_json = json.dumps(
                    {"format": result.audio_format or "wav", "data": result.audio_data},
                    ensure_ascii=False,
                )
                output_modality_actual = "text+audio" if output_content else "audio"
            else:
                output_modality_actual = "text"

            async with AsyncSessionLocal() as db:
                model_info = await db.get(Model, model_id)
                cost = CostCalculator.calculate_cost(
                    model_id, input_tokens, output_tokens,
                    model_info.input_price if model_info else None,
                    model_info.output_price if model_info else None
                )
        except Exception as e:
            status = 'error'
            error_message = str(e)[:2000]

        response_time_ms = int((time.time() - start_time) * 1000)

        async with AsyncSessionLocal() as db:
            job = await db.get(BatchJob, job_id)
            if not job or job.status == 'cancelled':
                return

            db.add(BatchJobResult(
                id=str(uuid.uuid4()),
                job_id=job_id,
                scenario_item_id=item.id,
                model_name=normalize_model_id(model_name),
                prompt=item.prompt,
                expected_answer=item.expected_answer,
                output_content=output_content if status == 'success' else None,
                output_audio=output_audio_json if status == 'success' else None,
                output_modality=output_modality_actual if status == 'success' else None,
                status=status,
                error_message=error_message,
                response_time_ms=response_time_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost if status == 'success' else None,
                is_delete=0
            ))

            if status == 'success':
                await BatchJobService._update_aggregates(
                    db, user_id, normalize_model_id(model_name), input_tokens, output_tokens, cost
                )
                job.completed_tasks = (job.completed_tasks or 0) + 1
            else:
                job.failed_tasks = (job.failed_tasks or 0) + 1

            await db.commit()

            payload = await ProgressPublisher.build_progress_payload(
                job_id, job.status, job.completed_tasks, job.total_tasks, job.failed_tasks,
                current_model=model_name, current_item_index=item_index, phase='generate',
            )
            await ProgressPublisher.publish(job_id, payload)

    async def _process_score_only_task(
        self,
        job_id: str,
        user_id: int,
        item_index: int,
        item: ScenarioItem,
        model_name: str,
    ) -> None:
        async with AsyncSessionLocal() as db:
            job = await db.get(BatchJob, job_id)
            if not job or job.status == 'cancelled':
                return

        text = (getattr(item, 'model_output', None) or '').strip()
        status = 'success' if text else 'error'
        error_message = None if text else '缺少待评文本 modelOutput'

        async with AsyncSessionLocal() as db:
            job = await db.get(BatchJob, job_id)
            if not job or job.status == 'cancelled':
                return
            db.add(BatchJobResult(
                id=str(uuid.uuid4()),
                job_id=job_id,
                scenario_item_id=item.id,
                model_name=normalize_model_id(model_name),
                prompt=item.prompt,
                expected_answer=item.expected_answer,
                output_content=text if status == 'success' else None,
                output_modality='text',
                status=status,
                error_message=error_message,
                response_time_ms=0,
                input_tokens=0,
                output_tokens=0,
                cost=None,
                is_delete=0,
            ))
            if status == 'success':
                job.completed_tasks = (job.completed_tasks or 0) + 1
            else:
                job.failed_tasks = (job.failed_tasks or 0) + 1
            await db.commit()

            payload = await ProgressPublisher.build_progress_payload(
                job_id, job.status, job.completed_tasks, job.total_tasks, job.failed_tasks,
                current_model=model_name, current_item_index=item_index, phase='import',
            )
            await ProgressPublisher.publish(job_id, payload)

    @staticmethod
    def _should_auto_score(job: BatchJob) -> bool:
        jt = getattr(job, 'job_type', None)
        if jt in ('oral_practice', 'score_only'):
            return True
        cfg = getattr(job, 'eval_config', None)
        if isinstance(cfg, dict):
            for key in ('listening', 'pronunciation', 'contentJudge'):
                section = cfg.get(key)
                if isinstance(section, dict) and section.get('enabled'):
                    return True
        return False

    async def _run_scoring_phase(self, job_id: str, user_id: int) -> None:
        job = await self.db.get(BatchJob, job_id)
        if not job or job.status == 'cancelled':
            return
        job.status = 'scoring'
        await self.db.commit()
        payload = await ProgressPublisher.build_progress_payload(
            job_id, 'scoring', 0, job.total_tasks or 0, job.failed_tasks or 0,
            event_type='progress', phase='scoring',
        )
        await ProgressPublisher.publish(job_id, payload)

        async with AsyncSessionLocal() as db:
            await OralScoringService(db).score_job(job_id, user_id)

        job = await self.db.get(BatchJob, job_id)
        if job:
            job.status = 'completed'
            await self.db.commit()

    async def score_job(self, job_id: str, user_id: int) -> None:
        await self._get_user_job(job_id, user_id)
        await self._run_scoring_phase(job_id, user_id)
        job = await self.db.get(BatchJob, job_id)
        if job:
            job.finished_at = datetime.now()
            await self.db.commit()

    @staticmethod
    async def _update_aggregates(
        db: AsyncSession,
        user_id: int,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        cost: Decimal
    ) -> None:
        model = await db.get(Model, model_name)
        if model:
            model.total_tokens = (model.total_tokens or 0) + input_tokens + output_tokens
            model.total_cost = Decimal(str(model.total_cost or 0)) + cost
            model.batch_call_count = (model.batch_call_count or 0) + 1

        result = await db.execute(
            select(UserModelStat).where(
                UserModelStat.user_id == user_id,
                UserModelStat.model_name == model_name
            )
        )
        stat = result.scalar_one_or_none()
        if stat:
            stat.call_count = (stat.call_count or 0) + 1
            stat.total_input_tokens = (stat.total_input_tokens or 0) + input_tokens
            stat.total_output_tokens = (stat.total_output_tokens or 0) + output_tokens
            stat.total_cost = Decimal(str(stat.total_cost or 0)) + cost
            stat.last_used_at = datetime.now()
        else:
            db.add(UserModelStat(
                user_id=user_id,
                model_name=model_name,
                call_count=1,
                total_input_tokens=input_tokens,
                total_output_tokens=output_tokens,
                total_cost=cost,
                last_used_at=datetime.now()
            ))

    async def _get_user_job(self, job_id: str, user_id: int) -> BatchJob:
        result = await self.db.execute(
            select(BatchJob).where(
                BatchJob.id == job_id,
                BatchJob.user_id == user_id,
                BatchJob.is_delete == 0
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        return job

    async def export_job_zip(self, job_id: str, user_id: int) -> bytes:
        await self._get_user_job(job_id, user_id)
        result = await self.db.execute(
            select(BatchJobResult).where(
                BatchJobResult.job_id == job_id,
                BatchJobResult.is_delete == 0,
            ).order_by(BatchJobResult.create_time.asc())
        )
        rows = list(result.scalars().all())
        buf = io.BytesIO()
        metadata = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in rows:
                safe_model = r.model_name.replace(":", "_").replace("/", "_")
                base = f"{r.scenario_item_id}_{safe_model}"
                meta = {
                    "id": r.id,
                    "modelName": r.model_name,
                    "status": r.status,
                    "outputModality": r.output_modality,
                    "evalScore": float(r.eval_score) if r.eval_score is not None else None,
                }
                if r.eval_detail:
                    try:
                        meta["evalDetail"] = json.loads(r.eval_detail)
                    except json.JSONDecodeError:
                        meta["evalDetailRaw"] = r.eval_detail
                if r.output_content:
                    zf.writestr(f"{base}.txt", r.output_content)
                    meta["textFile"] = f"{base}.txt"
                if r.output_audio:
                    try:
                        from app.utils.audio_pcm import output_audio_json_to_wav_bytes

                        audio_obj = json.loads(r.output_audio)
                        fmt = (audio_obj.get("format") or "wav").lower()
                        if fmt in ("pcm16", "pcm"):
                            wav_bytes, _ = output_audio_json_to_wav_bytes(r.output_audio)
                            zf.writestr(f"{base}.wav", wav_bytes)
                            meta["audioFile"] = f"{base}.wav"
                        else:
                            ext = fmt if fmt in ("wav", "mp3", "webm", "ogg") else "bin"
                            zf.writestr(f"{base}.{ext}", base64.b64decode(audio_obj.get("data", "")))
                            meta["audioFile"] = f"{base}.{ext}"
                    except Exception:
                        pass
                metadata.append(meta)
            zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        buf.seek(0)
        return buf.getvalue()

    def _to_job_vo(self, job: BatchJob, scenario_name: Optional[str]) -> BatchJobVO:
        return BatchJobVO(
            id=job.id,
            userId=job.user_id,
            scenarioId=job.scenario_id,
            scenarioName=scenario_name,
            models=job.models if isinstance(job.models, list) else [],
            status=job.status,
            totalTasks=job.total_tasks or 0,
            completedTasks=job.completed_tasks or 0,
            failedTasks=job.failed_tasks or 0,
            concurrency=job.concurrency or 3,
            outputModality=getattr(job, "output_modality", None) or "text",
            globalPrompt=getattr(job, "global_prompt", None),
            jobType=getattr(job, "job_type", None) or "batch_audio",
            systemPrompt=getattr(job, "system_prompt", None),
            userMessageMode=getattr(job, "user_message_mode", None) or "text_plus_audio",
            evalConfig=job.eval_config if isinstance(job.eval_config, dict) else None,
            errorSummary=job.error_summary,
            startedAt=job.started_at.isoformat() if job.started_at else None,
            finishedAt=job.finished_at.isoformat() if job.finished_at else None,
            createTime=job.create_time.isoformat() if job.create_time else None,
        )

    def _to_result_vo(self, r: BatchJobResult) -> BatchJobResultVO:
        return BatchJobResultVO(
            id=r.id,
            jobId=r.job_id,
            scenarioItemId=r.scenario_item_id,
            modelName=r.model_name,
            prompt=r.prompt,
            expectedAnswer=r.expected_answer,
            outputContent=r.output_content,
            outputAudio=r.output_audio,
            outputModality=r.output_modality,
            status=r.status,
            errorMessage=r.error_message,
            responseTimeMs=r.response_time_ms,
            inputTokens=r.input_tokens,
            outputTokens=r.output_tokens,
            cost=float(r.cost) if r.cost is not None else None,
            score=float(r.score) if r.score is not None else None,
            evalScore=float(r.eval_score) if r.eval_score is not None else None,
            evalDetail=r.eval_detail,
        )
