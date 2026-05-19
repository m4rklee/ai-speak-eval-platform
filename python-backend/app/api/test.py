"""
测试接口
"""
import time

from fastapi import APIRouter, Query
from starlette.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse, StreamChunkVO
from app.schemas.common import BaseResponse
from app.services.chat_service import ChatService


router = APIRouter(prefix="/test", tags=["测试接口"])

@router.post("/chat", response_model=BaseResponse[ChatResponse], summary="测试对话（非流式）")
async def test_chat(request: ChatRequest):
    """测试对话接口（非流式）"""
    content = await ChatService.simple_chat(
        message=request.message,
        model_name=request.model
    )
    response = ChatResponse(content=content, model=request.model)
    return BaseResponse(code=0, data=response, message="ok")

@router.api_route("/ai/stream", methods=["GET", "POST"], summary="AI流式对话")
async def test_ai_stream(
    prompt: str = Query(..., description="对话内容"),
    model: str = Query("deepseek/deepseek-chat", description="模型名称")
):
    """AI流式对话接口（支持GET和POST请求）"""
    async def generate():
        start_time = time.time()
        full_content = ""
        output_tokens = 0
        
        try:
            async for chunk in ChatService.stream_chat(
                message=prompt,
                model_name=model
            ):
                full_content += chunk
                output_tokens += len(chunk) // 4
                elapsed_ms = int((time.time() - start_time) * 1000)

                chunk_vo = StreamChunkVO(
                    modelName=model,
                    content=chunk,
                    fullContent=full_content,
                    outputTokens=output_tokens,
                    elapsedMs=elapsed_ms,
                    done=False,
                    hasError=False
                )
                yield f"data: {chunk_vo.model_dump_json()}\n\n"
            # 流结束，发送完成事件
            response_time_ms = int((time.time() - start_time) * 1000)
            final_chunk = StreamChunkVO(
                modelName=model,
                fullContent=full_content,
                outputTokens=output_tokens,
                responseTimeMs=response_time_ms,
                done=True,
                hasError=False
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
        except Exception as e:
            error_chunk = StreamChunkVO(
                modelName=model,
                error=str(e),
                hasError=True,
                done=True
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
