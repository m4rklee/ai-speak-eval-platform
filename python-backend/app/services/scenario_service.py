import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.models.scenario import Scenario
from app.models.scenario_item import ScenarioItem
from app.schemas.scenario import (
    ScenarioAddRequest,
    ScenarioImportRequest,
    ScenarioItemUpdateRequest,
    ScenarioItemVO,
    ScenarioUpdateRequest,
    ScenarioVO,
)


class ScenarioService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_scenarios(self, user_id: int) -> List[ScenarioVO]:
        result = await self.db.execute(
            select(Scenario).where(
                Scenario.is_delete == 0,
                (Scenario.source_type == 'system') | (Scenario.user_id == user_id)
            ).order_by(Scenario.source_type.asc(), Scenario.create_time.desc())
        )
        return [self._to_vo(s) for s in result.scalars().all()]

    async def get_scenario(self, scenario_id: str, user_id: int) -> Scenario:
        scenario = await self._get_accessible_scenario(scenario_id, user_id)
        return scenario

    async def get_scenario_detail(
        self, scenario_id: str, user_id: int, current: int = 1, page_size: int = 50
    ) -> Dict[str, Any]:
        scenario = await self._get_accessible_scenario(scenario_id, user_id)
        vo = self._to_vo(scenario)

        count_q = select(func.count()).select_from(ScenarioItem).where(
            ScenarioItem.scenario_id == scenario_id,
            ScenarioItem.is_delete == 0
        )
        total = (await self.db.execute(count_q)).scalar() or 0

        offset = (current - 1) * page_size
        items_result = await self.db.execute(
            select(ScenarioItem).where(
                ScenarioItem.scenario_id == scenario_id,
                ScenarioItem.is_delete == 0
            ).order_by(ScenarioItem.sort_order.asc(), ScenarioItem.create_time.asc())
            .offset(offset).limit(page_size)
        )
        items = [
            ScenarioItemVO.model_validate(item).model_dump(by_alias=True)
            for item in items_result.scalars().all()
        ]
        return {
            **vo.model_dump(by_alias=True),
            "items": items,
            "total": total,
            "current": current,
            "pageSize": page_size,
        }

    async def add_scenario(self, request: ScenarioAddRequest, user_id: int) -> str:
        scenario_id = str(uuid.uuid4())
        self.db.add(Scenario(
            id=scenario_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            source_type='custom',
            category=request.category,
            item_count=0,
            is_delete=0
        ))
        await self.db.commit()
        return scenario_id

    async def update_scenario(
        self, scenario_id: str, request: ScenarioUpdateRequest, user_id: int
    ) -> bool:
        scenario = await self._get_editable_scenario(scenario_id, user_id)
        if request.name is not None:
            scenario.name = request.name
        if request.description is not None:
            scenario.description = request.description
        if request.category is not None:
            scenario.category = request.category
        await self.db.commit()
        return True

    async def delete_scenario(self, scenario_id: str, user_id: int) -> bool:
        scenario = await self._get_editable_scenario(scenario_id, user_id)
        scenario.is_delete = 1
        await self.db.commit()
        return True

    async def import_items(
        self, scenario_id: str, request: ScenarioImportRequest, user_id: int
    ) -> int:
        scenario = await self._get_editable_scenario(scenario_id, user_id)
        for i, item in enumerate(request.items):
            input_type = item.input_type or "text"
            if item.audio_data:
                input_type = "text+audio" if item.prompt else "audio"
            model_out = (item.model_output or "").strip() or None
            self.db.add(ScenarioItem(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                prompt=item.prompt.strip(),
                expected_answer=item.expected_answer.strip(),
                model_output=model_out,
                category=item.category,
                input_type=input_type,
                audio_data=item.audio_data,
                audio_format=item.audio_format,
                audio_file_name=item.audio_file_name,
                sort_order=scenario.item_count + i,
                is_delete=0
            ))
        scenario.item_count += len(request.items)
        await self.db.commit()
        return len(request.items)

    async def list_items(
        self, scenario_id: str, user_id: int, current: int, page_size: int
    ) -> Dict[str, Any]:
        await self._get_accessible_scenario(scenario_id, user_id)
        count_q = select(func.count()).select_from(ScenarioItem).where(
            ScenarioItem.scenario_id == scenario_id,
            ScenarioItem.is_delete == 0
        )
        total = (await self.db.execute(count_q)).scalar() or 0
        offset = (current - 1) * page_size
        result = await self.db.execute(
            select(ScenarioItem).where(
                ScenarioItem.scenario_id == scenario_id,
                ScenarioItem.is_delete == 0
            ).order_by(ScenarioItem.sort_order.asc())
            .offset(offset).limit(page_size)
        )
        records = [
            ScenarioItemVO.model_validate(item).model_dump(by_alias=True)
            for item in result.scalars().all()
        ]
        return {"records": records, "total": total, "current": current, "pageSize": page_size}

    async def update_item(
        self, item_id: str, request: ScenarioItemUpdateRequest, user_id: int
    ) -> bool:
        item = await self._get_item_with_access(item_id, user_id)
        if request.prompt is not None:
            item.prompt = request.prompt
        if request.expected_answer is not None:
            item.expected_answer = request.expected_answer
        if request.category is not None:
            item.category = request.category
        if request.sort_order is not None:
            item.sort_order = request.sort_order
        await self.db.commit()
        return True

    async def delete_item(self, item_id: str, user_id: int) -> bool:
        item = await self._get_item_with_access(item_id, user_id)
        item.is_delete = 1
        scenario = await self.db.get(Scenario, item.scenario_id)
        if scenario:
            scenario.item_count = max(0, (scenario.item_count or 0) - 1)
        await self.db.commit()
        return True

    async def _get_accessible_scenario(self, scenario_id: str, user_id: int) -> Scenario:
        result = await self.db.execute(
            select(Scenario).where(Scenario.id == scenario_id, Scenario.is_delete == 0)
        )
        scenario = result.scalar_one_or_none()
        if not scenario:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "场景不存在")
        if scenario.source_type != 'system' and scenario.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限访问该场景")
        return scenario

    async def _get_editable_scenario(self, scenario_id: str, user_id: int) -> Scenario:
        scenario = await self._get_accessible_scenario(scenario_id, user_id)
        if scenario.source_type == 'system':
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "系统预设场景不可编辑")
        if scenario.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限")
        return scenario

    async def _get_item_with_access(self, item_id: str, user_id: int) -> ScenarioItem:
        result = await self.db.execute(
            select(ScenarioItem).where(ScenarioItem.id == item_id, ScenarioItem.is_delete == 0)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "用例不存在")
        await self._get_editable_scenario(item.scenario_id, user_id)
        return item

    def _to_vo(self, scenario: Scenario) -> ScenarioVO:
        return ScenarioVO(
            id=scenario.id,
            userId=scenario.user_id,
            name=scenario.name,
            description=scenario.description,
            sourceType=scenario.source_type,
            category=scenario.category,
            itemCount=scenario.item_count or 0,
            createTime=scenario.create_time.isoformat() if scenario.create_time else None,
        )
