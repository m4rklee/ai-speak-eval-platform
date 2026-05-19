"""语音评测流式服务"""
import json
import time
import uuid
from decimal import Decimal
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.model import Model
from app.providers.registry import get_provider
from app.schemas.conversation import AudioInput, StreamChunkVO, VoiceEvalRequest
from app.services.conversation_service import ConversationService
from app.utils.cost_calculator import CostCalculator
from app.utils.model_id import normalize_model_id, split_model_id, vendor_model_id


class VoiceEvalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._conv = ConversationService(db)

    async def eval_stream(self, request: VoiceEvalRequest, user_id: int) -> AsyncGenerator[str, None]:
        teacher_mode = request.teacher_mode
        if not request.model:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "模型不能为空")
        if not teacher_mode and not request.prompt.strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "提示词不能为空")
        if not request.audio_inputs:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请上传或录制音频")

        model_id = normalize_model_id(request.model)
        platform, _ = split_model_id(model_id)
        vendor_id = vendor_model_id(model_id)

        conversation_id = request.conversation_id or str(uuid.uuid4())
        if not request.conversation_id:
            self.db.add(Conversation(
                id=conversation_id,
                user_id=user_id,
                title=self._conv._generate_title(request.prompt),
                conversation_type="voice_eval",
                models=[model_id],
                total_tokens=0,
                total_cost=Decimal("0"),
                is_delete=0,
            ))
            await self.db.commit()

        user_index = await self._conv._save_user_message(
            conversation_id, user_id, request.prompt, None, request.audio_inputs, None
        )
        assistant_index = user_index + 1

        async for event in self._run_eval(
            conversation_id,
            user_id,
            model_id,
            platform,
            vendor_id,
            request.prompt,
            request.audio_inputs,
            assistant_index,
            request.require_audio_output or teacher_mode,
            teacher_mode=teacher_mode,
            system_prompt=request.system_prompt,
            user_message_mode=request.user_message_mode,
        ):
            yield event

    async def _run_eval(
        self,
        conversation_id: str,
        user_id: int,
        model_id: str,
        platform: str,
        vendor_id: str,
        prompt: str,
        audio_inputs: list[AudioInput],
        message_index: int,
        require_audio_output: bool,
        teacher_mode: bool = False,
        system_prompt: Optional[str] = None,
        user_message_mode: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        try:
            if teacher_mode:
                from app.utils.oral_practice import (
                    build_oral_practice_messages,
                    default_system_prompt,
                )

                mode = user_message_mode or "audio_only"
                messages = build_oral_practice_messages(
                    system_prompt=system_prompt or default_system_prompt(),
                    audio_inputs=audio_inputs,
                    item_prompt=prompt if mode != "audio_only" else None,
                    user_message_mode=mode,
                )
            else:
                messages = self._conv._build_messages(prompt, None, None, audio_inputs, None)
            provider = get_provider(platform)
            result = await provider.chat_completion(
                vendor_id,
                messages,
                require_audio_output=require_audio_output,
                max_tokens=4000,
                timeout=120.0,
            )
            accumulated = result.text or ""
            accumulated_audio = result.audio_data
            audio_format = result.audio_format
            input_tokens = result.input_tokens
            output_tokens = result.output_tokens

            partial = StreamChunkVO(
                conversation_id=conversation_id,
                model_name=model_id,
                content=accumulated,
                full_content=accumulated,
                audio_content=accumulated_audio,
                audio_format=audio_format,
                elapsed_ms=int((time.time() - start_time) * 1000),
                done=False,
                has_error=False,
            )
            yield f"data: {partial.model_dump_json(by_alias=True, exclude_none=True)}\n\n"

            output_modality = "text"
            if accumulated_audio:
                output_modality = "text+audio" if accumulated else "audio"

            async with AsyncSessionLocal() as model_db:
                model_info = await model_db.get(Model, model_id)

            response_time_ms = int((time.time() - start_time) * 1000)
            cost = CostCalculator.calculate_cost(
                model_id, input_tokens, output_tokens,
                model_info.input_price if model_info else None,
                model_info.output_price if model_info else None,
            )
            output_audio_json = None
            if accumulated_audio:
                output_audio_json = json.dumps(
                    {"format": audio_format or "wav", "data": accumulated_audio},
                    ensure_ascii=False,
                )

            async with AsyncSessionLocal() as db:
                db.add(ConversationMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message_index=message_index,
                    role="assistant",
                    model_name=model_id,
                    content=accumulated,
                    response_time_ms=response_time_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    output_audio=output_audio_json,
                    output_modality=output_modality,
                    is_delete=0,
                ))
                if model_info:
                    model_info.total_tokens = (model_info.total_tokens or 0) + input_tokens + output_tokens
                conv = await db.get(Conversation, conversation_id)
                if conv:
                    conv.total_tokens = (conv.total_tokens or 0) + input_tokens + output_tokens
                    conv.total_cost = (conv.total_cost or Decimal("0")) + cost
                await db.commit()

            done_vo = StreamChunkVO(
                conversation_id=conversation_id,
                model_name=model_id,
                full_content=accumulated,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=float(cost),
                response_time_ms=response_time_ms,
                audio_content=accumulated_audio,
                audio_format=audio_format,
                output_modality=output_modality,
                done=True,
                has_error=False,
            )
            yield f"data: {done_vo.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
        except Exception as e:
            err = StreamChunkVO(
                conversation_id=conversation_id,
                model_name=model_id,
                error=str(e),
                done=True,
                has_error=True,
            )
            yield f"data: {err.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
