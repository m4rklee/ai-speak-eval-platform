import json
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.providers.registry import get_provider, list_platforms
from app.schemas.model import ModelListQuery, ModelVO
from app.utils.model_dedupe import merge_model_vos, model_matches_platform_filter
from app.utils.model_id import normalize_model_id, split_model_id


class ModelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_models(self, platform: str = "all") -> dict[str, int]:
        targets = list_platforms() if platform == "all" else [platform]
        counts: dict[str, int] = {}
        for p in targets:
            provider = get_provider(p)
            normalized_list = await provider.fetch_models()
            count = 0
            for nm in normalized_list:
                result = await self.db.execute(select(Model).where(Model.id == nm.composite_id))
                existing = result.scalar_one_or_none()
                input_json = json.dumps(nm.input_modalities, ensure_ascii=False)
                output_json = json.dumps(nm.output_modalities, ensure_ascii=False)
                if existing:
                    existing.platform = nm.platform
                    existing.name = nm.name[:200]
                    existing.description = nm.description
                    existing.provider = nm.provider
                    existing.context_length = nm.context_length
                    existing.modality = nm.modality
                    existing.input_modalities = input_json
                    existing.output_modalities = output_json
                    existing.input_price = nm.input_price
                    existing.output_price = nm.output_price
                    existing.released_at = nm.released_at
                    existing.model_type = nm.model_type
                    existing.recommended = nm.recommended if nm.recommended else existing.recommended
                    existing.is_china = nm.is_china
                    existing.raw_data = nm.raw_data
                    existing.is_delete = 0
                else:
                    self.db.add(Model(
                        id=nm.composite_id,
                        platform=nm.platform,
                        name=nm.name[:200],
                        description=nm.description,
                        provider=nm.provider,
                        context_length=nm.context_length,
                        modality=nm.modality,
                        input_modalities=input_json,
                        output_modalities=output_json,
                        input_price=nm.input_price,
                        output_price=nm.output_price,
                        released_at=nm.released_at,
                        model_type=nm.model_type,
                        recommended=nm.recommended,
                        is_china=nm.is_china,
                        raw_data=nm.raw_data,
                        is_delete=0,
                    ))
                count += 1
            await self.db.commit()
            counts[p] = count
        return counts

    async def sync_models_from_openrouter(self) -> int:
        result = await self.sync_models("openrouter")
        return result.get("openrouter", 0)

    async def list_models(self, query: Optional[ModelListQuery] = None) -> list[ModelVO]:
        q = select(Model).where(Model.is_delete == 0)
        if query:
            if query.model_type:
                q = q.where(Model.model_type == query.model_type)
            if query.keyword:
                kw = f"%{query.keyword}%"
                q = q.where(or_(Model.name.like(kw), Model.id.like(kw), Model.description.like(kw)))
        result = await self.db.execute(q)
        models = list(result.scalars().all())
        vos = merge_model_vos([self._to_vo(m) for m in models])
        if query:
            if query.platform:
                vos = [v for v in vos if model_matches_platform_filter(v, query.platform)]
            if query.input_modality:
                vos = [v for v in vos if query.input_modality in v.input_modalities]
            if query.output_modality:
                vos = [v for v in vos if query.output_modality in v.output_modalities]
            desc = (query.sort_order or "asc").lower() == "desc"

            def _num(v) -> float:
                try:
                    return float(v) if v is not None else float("-inf")
                except (TypeError, ValueError):
                    return float("-inf")

            if query.sort_by == "releasedAt":
                # 无发布时间的模型排在末尾
                sentinel = "0000-01-01" if desc else "9999-12-31"
                vos.sort(key=lambda x: x.released_at or sentinel, reverse=desc)
            elif query.sort_by == "inputPrice":
                vos.sort(key=lambda x: _num(x.input_price), reverse=desc)
            elif query.sort_by == "outputPrice":
                vos.sort(key=lambda x: _num(x.output_price), reverse=desc)
            elif query.sort_by == "contextLength":
                vos.sort(key=lambda x: int(x.context_length or 0), reverse=desc)
            else:
                vos.sort(key=lambda x: x.name, reverse=desc)
        else:
            vos.sort(key=lambda x: (-x.is_china, -x.recommended, x.name))
        return vos

    def _to_vo(self, model: Model) -> ModelVO:
        released = None
        if model.released_at:
            released = model.released_at.isoformat() if isinstance(model.released_at, datetime) else str(model.released_at)
        return ModelVO(
            id=model.id,
            platform=model.platform or split_model_id(model.id)[0],
            name=model.name,
            description=model.description,
            provider=model.provider,
            contextLength=model.context_length,
            modality=model.modality,
            inputModalities=model.input_modalities,
            outputModalities=model.output_modalities,
            inputPrice=model.input_price,
            outputPrice=model.output_price,
            releasedAt=released,
            modelType=model.model_type,
            recommended=model.recommended or 0,
            isChina=model.is_china or 0,
            totalTokens=int(model.total_tokens or 0),
            batchCallCount=int(model.batch_call_count or 0),
        )
