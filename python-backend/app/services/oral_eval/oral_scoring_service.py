"""口语练习 Step2：听力 + 发音 + 内容评分"""
import json
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.batch_job import BatchJob
from app.models.batch_job_result import BatchJobResult
from app.services.oral_eval.content_judge import score_content
from app.services.oral_eval.listening_scorer import score_listening
from app.services.oral_eval.pronunciation_http import HttpPronunciationProvider
from app.services.oral_eval.unified_eval_runner import score_batch_rows, validate_unified_eval_paths
from app.services.oral_eval.unified_subprocess_provider import UnifiedSubprocessPronunciationProvider
from app.services.progress_publisher import ProgressPublisher
from app.utils.audio_pcm import output_audio_json_to_wav_bytes
from app.utils.oral_practice import default_eval_config


class OralScoringService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _pronunciation_provider_mode(pron_cfg: dict[str, Any]) -> str:
        """Return 'unified' | 'http' | 'skip'."""
        if pron_cfg.get("enabled") is False:
            return "skip"
        provider = (pron_cfg.get("provider") or "").strip().lower()
        base_url = (pron_cfg.get("baseUrl") or "").strip()
        settings = get_settings()
        if not base_url:
            base_url = (settings.PRONUNCIATION_EVAL_URL or "").strip()
        if provider == "http" or (base_url and provider != "unified"):
            return "http" if base_url else "skip"
        if provider == "unified" or settings.UNIFIED_EVAL_ENABLED:
            ok, _ = validate_unified_eval_paths()
            return "unified" if ok else "skip"
        return "skip"

    async def score_job(self, job_id: str, user_id: int) -> None:
        job = await self._get_job(job_id, user_id)
        eval_cfg = job.eval_config if isinstance(job.eval_config, dict) else default_eval_config()
        if job.job_type == "score_only":
            pass
        elif job.job_type not in ("oral_practice", "batch_audio") and not eval_cfg:
            return

        result = await self.db.execute(
            select(BatchJobResult).where(
                BatchJobResult.job_id == job_id,
                BatchJobResult.is_delete == 0,
                BatchJobResult.status == "success",
            )
        )
        rows = list(result.scalars().all())
        total = len(rows)
        if total == 0:
            return

        pron_cfg = eval_cfg.get("pronunciation") or {}
        pron_mode = self._pronunciation_provider_mode(pron_cfg)
        pron_cache: dict[str, dict[str, Any]] = {}

        if pron_mode == "unified":
            await ProgressPublisher.publish(
                job_id,
                await ProgressPublisher.build_progress_payload(
                    job_id,
                    "scoring",
                    0,
                    total,
                    0,
                    event_type="progress",
                    phase="pronunciation_batch",
                ),
            )
            pron_cache = await score_batch_rows(rows, job_id=job_id, pron_cfg=pron_cfg)

        done = 0
        for row in rows:
            detail = await self._score_one_row(
                row,
                eval_cfg,
                pron_cache=pron_cache if pron_mode == "unified" else None,
                pron_mode=pron_mode,
            )
            row.eval_detail = json.dumps(detail, ensure_ascii=False)
            row.eval_score = Decimal(str(detail.get("composite", 0)))
            done += 1
            await self.db.commit()
            payload = await ProgressPublisher.build_progress_payload(
                job_id,
                "scoring",
                done,
                total,
                0,
                event_type="progress",
                phase="scoring",
            )
            await ProgressPublisher.publish(job_id, payload)

    async def _score_one_row(
        self,
        row: BatchJobResult,
        eval_cfg: dict[str, Any],
        *,
        pron_cache: Optional[dict[str, dict[str, Any]]] = None,
        pron_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        scores_for_composite: list[tuple[float, float]] = []
        weights = eval_cfg.get("weights") or {}

        listen_cfg = eval_cfg.get("listening") or {}
        if listen_cfg.get("enabled", True):
            listen = score_listening(
                row.output_content or "",
                row.expected_answer or "",
                mode=listen_cfg.get("mode", "normalized_match"),
            )
            detail["listening"] = listen
            w = float(weights.get("listening", 0.35))
            scores_for_composite.append((listen["score"] * 100, w))

        pron_cfg = eval_cfg.get("pronunciation") or {}
        if pron_cfg.get("enabled", True):
            mode = pron_mode or self._pronunciation_provider_mode(pron_cfg)
            if mode == "unified" and pron_cache is not None:
                rid = str(row.id) if row.id else ""
                detail["pronunciation"] = pron_cache.get(
                    rid,
                    {"status": "skipped", "reason": "批量统一评测未返回该条结果"},
                )
            elif mode != "skip":
                detail["pronunciation"] = await self._score_pronunciation(row, pron_cfg, mode=mode)
            else:
                ok, reason = validate_unified_eval_paths()
                detail["pronunciation"] = {
                    "status": "skipped",
                    "reason": reason or "未配置发音评测（provider=http 需 baseUrl，或启用 unified）",
                }

            pron = detail.get("pronunciation") or {}
            if pron.get("status") == "ok":
                avg = (
                    pron.get("accuracy", 0)
                    + pron.get("fluency", 0)
                    + pron.get("naturalness", 0)
                ) / 3.0
                w = float(weights.get("pronunciation", 0.35))
                scores_for_composite.append((avg, w))

        judge_cfg = eval_cfg.get("contentJudge") or {}
        if judge_cfg.get("enabled", True):
            settings = get_settings()
            judge_model = (
                judge_cfg.get("judgeModel")
                or getattr(settings, "ORAL_EVAL_JUDGE_MODEL", "")
                or "openrouter:openai/gpt-4o-mini"
            )
            try:
                content = await score_content(
                    item_prompt=row.prompt or "",
                    expected_answer=row.expected_answer or "",
                    model_output=row.output_content or "",
                    judge_model=judge_model,
                    rubric=judge_cfg.get("rubric") or "",
                    max_score=int(judge_cfg.get("maxScore", 5)),
                )
                detail["content"] = content
                if content.get("composite") is not None:
                    normalized = float(content["composite"])
                else:
                    max_s = content.get("max", 5) or 5
                    normalized = (content.get("score", 0) / max_s) * 100
                w = float(weights.get("content", 0.3))
                scores_for_composite.append((normalized, w))
            except Exception as e:
                detail["content"] = {"status": "error", "reason": str(e)[:500]}

        total_w = sum(w for _, w in scores_for_composite) or 1.0
        composite = sum(s * w for s, w in scores_for_composite) / total_w
        detail["composite"] = round(composite, 2)
        return detail

    async def _score_pronunciation(
        self,
        row: BatchJobResult,
        pron_cfg: dict[str, Any],
        *,
        mode: Optional[str] = None,
    ) -> dict[str, Any]:
        mode = mode or self._pronunciation_provider_mode(pron_cfg)
        if mode == "skip":
            ok, reason = validate_unified_eval_paths()
            return {
                "status": "skipped",
                "reason": reason or "未配置发音评测服务",
            }

        if not row.output_audio:
            return {"status": "skipped", "reason": "无输出音频"}

        ref_from = pron_cfg.get("refTextFrom", "output_content")
        ref_text = row.output_content if ref_from == "output_content" else row.expected_answer
        if not (ref_text or "").strip():
            ref_text = row.expected_answer or row.prompt or ""

        try:
            wav_bytes, _ = output_audio_json_to_wav_bytes(row.output_audio)
            if mode == "http":
                base_url = (pron_cfg.get("baseUrl") or "").strip()
                if not base_url:
                    base_url = (get_settings().PRONUNCIATION_EVAL_URL or "").strip()
                provider = HttpPronunciationProvider(base_url)
                return await provider.score(wav_bytes, ref_text)
            provider = UnifiedSubprocessPronunciationProvider()
            return await provider.score(wav_bytes, ref_text)
        except Exception as e:
            return {"status": "error", "reason": str(e)[:500]}

    async def score_inline(
        self,
        *,
        prompt: str,
        expected_answer: str,
        output_content: str,
        output_audio: Optional[str] = None,
        eval_cfg: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """单条调试评分（语音工作台）"""
        cfg = eval_cfg if isinstance(eval_cfg, dict) else default_eval_config()
        row = BatchJobResult(
            prompt=prompt,
            expected_answer=expected_answer,
            output_content=output_content,
            output_audio=output_audio,
            status="success",
        )
        pron_cfg = cfg.get("pronunciation") or {}
        pron_mode = self._pronunciation_provider_mode(pron_cfg)
        return await self._score_one_row(row, cfg, pron_mode=pron_mode)

    async def _get_job(self, job_id: str, user_id: int) -> BatchJob:
        result = await self.db.execute(
            select(BatchJob).where(
                BatchJob.id == job_id,
                BatchJob.user_id == user_id,
                BatchJob.is_delete == 0,
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            from app.core.errors import BusinessException, ErrorCode

            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        return job
