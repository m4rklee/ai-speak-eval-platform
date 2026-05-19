"""
对话服务
"""
import asyncio
import base64
import json
import time
import uuid
from decimal import Decimal
from typing import Any, AsyncGenerator, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.core.openrouter_config import get_openrouter_client
from app.utils.model_id import normalize_model_id, split_model_id, vendor_model_id
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.model import Model
from app.schemas.conversation import AudioInput, FileInput, PromptLabRequest, SideBySideRequest, StreamChunkVO
from app.utils.cost_calculator import CostCalculator


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def side_by_side_stream(
        self,
        request: SideBySideRequest,
        user_id: int
    ) -> AsyncGenerator[str, None]:
        """Side-by-Side 多模型并排对比（SSE 流式响应）"""
        # 1. 参数校验
        self.validate_side_by_side_request(request)

        # 2. 创建或获取对话记录
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title=self._generate_title(request.prompt),
                conversation_type="side_by_side",
                models=request.models,
                total_tokens=0,
                total_cost=Decimal('0'),
                is_delete=0
            )
            self.db.add(conversation)
            await self.db.commit()
        else:
            result = await self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                    Conversation.is_delete == 0
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "对话不存在")

        # 3. 保存用户消息，获取 messageIndex
        user_message_index = await self._save_user_message(
            conversation_id, user_id, request.prompt, request.image_urls, request.audio_inputs, request.file_inputs
        )
        assistant_message_index = user_message_index + 1

        # 4. 为每个模型创建独立的流
        streams = []
        for model_name in request.models:
            stream = self._stream_single_model(
                conversation_id, user_id, model_name,
                request.prompt, assistant_message_index, None,
                request.image_urls, request.audio_inputs, request.file_inputs, bool(request.web_search_enabled)
            )
            streams.append(stream)

        # 5. 合并所有流并返回
        async for event in self._merge_streams(streams, request.models):
            yield event

    def validate_side_by_side_request(self, request: SideBySideRequest) -> None:
        """校验 Side-by-Side 请求参数"""
        if not request.models or len(request.models) == 0:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "模型列表不能为空")
        if len(request.models) > 8:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "最多支持8个模型")
        if not request.prompt or not request.prompt.strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "提示词不能为空")

    def validate_prompt_lab_request(self, request: PromptLabRequest) -> None:
        """校验 Prompt Lab 请求参数"""
        if not request.model or not request.model.strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "模型不能为空")
        if not request.prompts or len(request.prompts) < 2:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "至少需要2个提示词变体")
        if len(request.prompts) > 5:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "最多支持5个提示词变体")
        for i, prompt in enumerate(request.prompts):
            if not prompt or not prompt.strip():
                raise BusinessException(ErrorCode.PARAMS_ERROR, f"变体 {i + 1} 的提示词不能为空")

    async def prompt_lab_stream(
        self,
        request: PromptLabRequest,
        user_id: int
    ) -> AsyncGenerator[str, None]:
        """Prompt Lab 提示词变体对比（SSE 流式响应）"""
        self.validate_prompt_lab_request(request)

        # 1. 创建或获取对话记录
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title=self._generate_title(request.prompts[0]),
                conversation_type="prompt_lab",
                models=[request.model],
                total_tokens=0,
                total_cost=Decimal('0'),
                is_delete=0
            )
            self.db.add(conversation)
            await self.db.commit()
        else:
            result = await self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                    Conversation.is_delete == 0
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "对话不存在")

        # 2. 保存用户消息（合并所有变体 prompts）
        merged_prompt = "\n\n".join(
            f"[变体 {i + 1}] {p}" for i, p in enumerate(request.prompts)
        )
        user_message_index = await self._save_user_message(
            conversation_id, user_id, merged_prompt,
            request.image_urls, request.audio_inputs, request.file_inputs
        )
        assistant_message_index = user_message_index + 1

        # 3. 为每个 prompt 变体创建独立的流
        streams = []
        for i, prompt in enumerate(request.prompts):
            stream = self._stream_single_model(
                conversation_id, user_id, request.model,
                prompt, assistant_message_index, i,
                request.image_urls, request.audio_inputs, request.file_inputs,
                bool(request.web_search_enabled)
            )
            streams.append(stream)

        # 4. 合并所有流并返回
        async for event in self._merge_streams(streams, [request.model] * len(request.prompts)):
            yield event

    async def _stream_single_model(
        self,
        conversation_id: str,
        user_id: int,
        model_name: str,
        prompt: str,
        message_index: int,
        variant_index: Optional[int],
        image_urls: Optional[List[str]],
        audio_inputs: Optional[List[AudioInput]],
        file_inputs: Optional[List[FileInput]],
        web_search_enabled: bool,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """调用单个模型并流式返回结果"""
        # ========== 第一步：初始化计数器 ==========
        start_time = time.time()
        accumulated_content = ""
        accumulated_reasoning = ""
        input_tokens = CostCalculator.estimate_tokens(prompt)
        output_tokens = 0
        thinking_start_time = None

        try:
            # ========== 第二步：加载历史消息构建上下文 ==========
            async with AsyncSessionLocal() as history_db:
                history_messages = await self._get_history_messages_for_context(
                    history_db, conversation_id, message_index, variant_index, model_name
                )

            messages: list[dict[str, Any]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            for msg in history_messages:
                if msg.role == "user":
                    parsed_prompt, parsed_images, parsed_audios, parsed_files = self._parse_user_message_content(msg.content)
                    if parsed_images or parsed_audios or parsed_files:
                        messages.extend(self._build_messages(parsed_prompt, None, parsed_images, parsed_audios, parsed_files))
                    else:
                        messages.append({"role": "user", "content": parsed_prompt})
                elif msg.role == "assistant":
                    messages.append({"role": "assistant", "content": msg.content})

            messages.extend(self._build_messages(prompt, None, image_urls, audio_inputs, file_inputs))

            async with AsyncSessionLocal() as model_db:
                model_info = await model_db.get(Model, model_name)

            # ========== 第三步：流式调用 AI 模型 ==========
            client = get_openrouter_client()
            model_id = normalize_model_id(model_name)
            platform, _ = split_model_id(model_id)
            vendor_id = vendor_model_id(model_id)
            create_params = {
                "model": vendor_id,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
                "timeout": 60.0,
                "stream_options": {"include_usage": True},
                "extra_headers": {
                    "HTTP-Referer": "https://codefather.cn",
                    "X-Title": "AI Evaluation Platform"
                }
            }
            if web_search_enabled:
                create_params["extra_body"] = {"plugins": [{"id": "web"}]}
            stream = await client.chat.completions.create(**create_params)

            # ========== 第四步：处理流式数据 ==========
            stream_iter = stream.__aiter__()

            while True:
                if (time.time() - start_time) > 120:
                    break

                try:
                    chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=30)
                except StopAsyncIteration:
                    break

                usage = getattr(chunk, "usage", None)
                if usage:
                    input_tokens = usage.prompt_tokens or input_tokens
                    output_tokens = usage.completion_tokens or output_tokens

                if not chunk.choices or len(chunk.choices) == 0:
                    continue

                delta = chunk.choices[0].delta
                delta_reasoning = getattr(delta, "reasoning", None)

                if delta_reasoning:
                    accumulated_reasoning += delta_reasoning
                    if thinking_start_time is None:
                        thinking_start_time = time.time()

                    reasoning_vo = StreamChunkVO(
                        conversation_id=conversation_id,
                        model_name=model_name,
                        variant_index=variant_index,
                        reasoning=accumulated_reasoning,
                        has_reasoning=True,
                        elapsed_ms=int((time.time() - start_time) * 1000),
                        done=False,
                        has_error=False
                    )
                    yield f"data: {reasoning_vo.model_dump_json(by_alias=True, exclude_none=True)}\n\n"

                if delta.content:
                    content = delta.content
                    accumulated_content += content
                    output_tokens += CostCalculator.estimate_tokens(content)
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    chunk_vo = StreamChunkVO(
                        conversation_id=conversation_id,
                        model_name=model_name,
                        variant_index=variant_index,
                        content=content,
                        full_content=accumulated_content,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        elapsed_ms=elapsed_ms,
                        done=False,
                        has_error=False
                    )
                    yield f"data: {chunk_vo.model_dump_json(by_alias=True, exclude_none=True)}\n\n"

            # ========== 第五步：流结束，保存到数据库 ==========
            response_time_ms = int((time.time() - start_time) * 1000)
            cost = CostCalculator.calculate_cost(
                model_name, input_tokens, output_tokens,
                model_info.input_price if model_info else None,
                model_info.output_price if model_info else None
            )

            async with AsyncSessionLocal() as independent_db:
                await self._save_assistant_message(
                    independent_db, conversation_id, user_id,
                    message_index, model_name, variant_index,
                    accumulated_content, input_tokens, output_tokens,
                    cost, response_time_ms, accumulated_reasoning or None
                )

            done_vo = StreamChunkVO(
                conversation_id=conversation_id,
                model_name=model_name,
                variant_index=variant_index,
                full_content=accumulated_content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=float(cost),
                response_time_ms=response_time_ms,
                done=True, has_error=False,
                reasoning=accumulated_reasoning or None,
                has_reasoning=bool(accumulated_reasoning),
                thinking_time=int(time.time() - thinking_start_time) if thinking_start_time else None
            )
            yield f"data: {done_vo.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
        except Exception as e:
            error_vo = StreamChunkVO(
                conversation_id=conversation_id,
                model_name=model_name,
                variant_index=variant_index,
                error=str(e),
                has_error=True, done=True
            )
            yield f"data: {error_vo.model_dump_json(by_alias=True, exclude_none=True)}\n\n"

    async def _merge_streams(
        self,
        streams: list[AsyncGenerator[str, None]],
        models: list[str]
    ) -> AsyncGenerator[str, None]:
        """合并多个流式响应"""
        # 为每个流创建一个队列
        queues = {i: asyncio.Queue() for i in range(len(streams))}
        done_flags = {i: False for i in range(len(streams))}

        async def consume_stream(idx: int, stream: AsyncGenerator[str, None], model_name: str):
            """消费单个流，把事件放入队列"""
            try:
                async for event in stream:
                    await queues[idx].put(event)
            except Exception as e:
                error_vo = StreamChunkVO(model_name=model_name, error=str(e), done=True, has_error=True)
                await queues[idx].put(
                    f"data: {error_vo.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
                )
            finally:
                await queues[idx].put(None)

        # 启动所有消费任务（并行执行）
        consumers = [
            asyncio.create_task(consume_stream(i, stream, models[i]))
            for i, stream in enumerate(streams)
        ]

        merge_deadline = time.time() + 130

        # 轮询所有队列，谁先有数据谁优先发
        while not all(done_flags.values()):
            if time.time() > merge_deadline:
                for i in range(len(consumers)):
                    if not done_flags[i]:
                        consumers[i].cancel()
                break

            for idx, queue in queues.items():
                if done_flags[idx]:
                    continue
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.01)
                    if event is None:
                        done_flags[idx] = True
                        continue
                    yield event
                except asyncio.TimeoutError:
                    continue

        await asyncio.gather(*consumers, return_exceptions=True)

    async def _save_user_message(
        self,
        conversation_id: str,
        user_id: int,
        prompt: str,
        image_urls: Optional[list[str]],
        audio_inputs: Optional[list[AudioInput]],
        file_inputs: Optional[list[FileInput]] = None
    ) -> int:
        """保存用户消息并返回消息序号"""
        result = await self.db.execute(
            select(func.max(ConversationMessage.message_index)).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.is_delete == 0
            )
        )
        max_index = result.scalar()
        message_index = 0 if max_index is None else max_index + 1
        has_attachments = image_urls or audio_inputs or file_inputs
        content = prompt if not has_attachments else json.dumps(
            {
                "prompt": prompt,
                "imageUrls": image_urls or [],
                "audioInputs": [
                    {"name": audio.name, "format": audio.format}
                    for audio in (audio_inputs or [])
                ],
                "fileInputs": [
                    {"name": file.name, "format": file.format, "mimeType": file.mime_type}
                    for file in (file_inputs or [])
                ]
            },
            ensure_ascii=False
        )

        self.db.add(ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            message_index=message_index,
            role="user",
            content=content,
            is_delete=0
        ))
        await self.db.commit()
        return message_index

    async def _save_assistant_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: int,
        message_index: int,
        model_name: str,
        variant_index: Optional[int],
        content: str,
        input_tokens: int,
        output_tokens: int,
        cost: Decimal,
        response_time_ms: int,
        reasoning: Optional[str]
    ) -> None:
        """保存模型回复和消耗指标"""
        del variant_index
        db.add(ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            message_index=message_index,
            role="assistant",
            model_name=model_name,
            content=content,
            response_time_ms=response_time_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            reasoning=reasoning,
            is_delete=0
        ))

        conversation = await db.get(Conversation, conversation_id)
        if conversation:
            conversation.total_tokens = (conversation.total_tokens or 0) + input_tokens + output_tokens
            conversation.total_cost = Decimal(str(conversation.total_cost or 0)) + cost

        model = await db.get(Model, model_name)
        if model:
            model.total_tokens = (model.total_tokens or 0) + input_tokens + output_tokens
            model.total_cost = Decimal(str(model.total_cost or 0)) + cost

        await db.commit()

    async def _get_history_messages_for_context(
        self,
        db: AsyncSession,
        conversation_id: str,
        message_index: int,
        variant_index: Optional[int],
        model_name: Optional[str] = None
    ) -> list[ConversationMessage]:
        """获取历史消息用于构建上下文"""
        del variant_index
        current_user_message_index = message_index - 1
        result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.message_index < current_user_message_index,
                ConversationMessage.is_delete == 0
            ).order_by(ConversationMessage.message_index.asc(), ConversationMessage.create_time.asc())
        )
        messages = list(result.scalars().all())
        return [
            msg for msg in messages
            if msg.role == "user" or (msg.role == "assistant" and msg.model_name == model_name)
        ]

    async def _calculate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> Decimal:
        """根据模型价格估算成本"""
        model = await self.db.get(Model, model_name)
        if not model:
            return Decimal('0')

        input_price = Decimal(str(model.input_price or 0))
        output_price = Decimal(str(model.output_price or 0))
        cost = (Decimal(input_tokens) / Decimal('1000000') * input_price)
        cost += (Decimal(output_tokens) / Decimal('1000000') * output_price)
        return cost.quantize(Decimal('0.000001'))

    def _parse_user_message_content(
        self, content: str
    ) -> tuple[str, Optional[list[str]], Optional[list[AudioInput]], Optional[list[FileInput]]]:
        """解析用户消息内容，提取多模态附件"""
        try:
            data = json.loads(content)
            if isinstance(data, dict) and ("imageUrls" in data or "audioInputs" in data or "fileInputs" in data):
                prompt = data.get("prompt", "")
                image_urls = data.get("imageUrls") or None
                audio_inputs = [AudioInput(**a) for a in data.get("audioInputs", [])] if data.get("audioInputs") else None
                file_inputs = [FileInput(**f) for f in data.get("fileInputs", [])] if data.get("fileInputs") else None
                return prompt, image_urls, audio_inputs, file_inputs
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return content, None, None, None

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
        image_urls: Optional[list[str]],
        audio_inputs: Optional[list[AudioInput]],
        file_inputs: Optional[list[FileInput]] = None
    ) -> list[dict[str, Any]]:
        """构建 OpenAI 兼容消息"""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if image_urls or audio_inputs or file_inputs:
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            content.extend(
                {"type": "image_url", "image_url": {"url": url}}
                for url in (image_urls or [])
            )
            content.extend(
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": audio.data,
                        "format": audio.format
                    }
                }
                for audio in (audio_inputs or [])
            )
            # 处理文件输入：文本类直接解码插入，PDF/二进制使用 image_url（vision 模型支持）
            TEXT_FORMATS = {
                "txt", "md", "json", "csv", "html", "css", "js", "ts", "py",
                "java", "cpp", "c", "go", "rs", "xml", "yaml", "yml", "log"
            }
            for file in (file_inputs or []):
                if file.format.lower() in TEXT_FORMATS:
                    try:
                        text_content = base64.b64decode(file.data).decode("utf-8")
                        content.append({
                            "type": "text",
                            "text": f"\n--- File: {file.name or 'untitled.' + file.format} ---\n{text_content}\n---\n"
                        })
                    except Exception:
                        content.append({
                            "type": "text",
                            "text": f"\n[File: {file.name or 'untitled.' + file.format} - decode error]\n"
                        })
                else:
                    mime = file.mime_type or f"application/{file.format}"
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{file.data}"}
                    })
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})
        return messages

    def _generate_title(self, prompt: str) -> str:
        """根据提示词生成对话标题"""
        title = prompt.strip().replace("\n", " ")
        return title[:30] if len(title) > 30 else title
