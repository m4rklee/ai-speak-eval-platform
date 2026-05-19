"""
对话相关的请求和响应模型
"""
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    model: str = Field(default="deepseek/deepseek-chat", description="模型名称")

class ChatResponse(BaseModel):
    """对话响应"""
    content: str = Field(..., description="模型回复内容")
    model: str = Field(..., description="使用的模型名称")

class StreamChunkVO(BaseModel):
    """流式响应数据块VO"""
    conversationId: Optional[str] = Field(None, description="对话ID")
    modelName: Optional[str] = Field(None, description="模型名称")
    variantIndex: Optional[int] = Field(None, description="变体索引")
    content: Optional[str] = Field(None, description="内容片段")
    fullContent: Optional[str] = Field(None, description="完整内容")
    inputTokens: Optional[int] = Field(None, description="输入Token数")
    outputTokens: Optional[int] = Field(None, description="输出Token数")
    totalTokens: Optional[int] = Field(None, description="总Token数")
    elapsedMs: Optional[int] = Field(None, description="已耗时（毫秒）")
    responseTimeMs: Optional[int] = Field(None, description="响应时间（毫秒）")
    cost: Optional[float] = Field(None, description="成本（USD）")
    done: Optional[bool] = Field(False, description="是否完成")
    error: Optional[str] = Field(None, description="错误信息")
    hasError: Optional[bool] = Field(False, description="是否发生错误")
    reasoning: Optional[str] = Field(None, description="思考过程")
    hasReasoning: Optional[bool] = Field(False, description="是否有思考过程")
    thinkingTime: Optional[int] = Field(None, description="思考时间（秒）")
