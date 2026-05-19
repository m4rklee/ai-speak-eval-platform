"""
对话相关请求和响应模型
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class AudioInput(BaseModel):
    """音频输入"""
    data: str = Field(..., description="base64 编码后的音频内容")
    format: str = Field(..., description="音频格式，如 wav/mp3/m4a")
    name: Optional[str] = Field(None, description="文件名")


class FileInput(BaseModel):
    """文件输入（PDF/文档等）"""
    data: str = Field(..., description="base64 编码后的文件内容")
    format: str = Field(..., description="文件格式，如 pdf/txt/md")
    name: Optional[str] = Field(None, description="文件名")
    mime_type: Optional[str] = Field(None, alias="mimeType", description="MIME类型")


class SideBySideRequest(BaseModel):
    """Side-by-Side 多模型并排对比请求"""
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    models: List[str] = Field(..., description="模型列表（1-8个）")
    prompt: str = Field(..., description="提示词")
    image_urls: Optional[List[str]] = Field(None, alias="imageUrls")
    audio_inputs: Optional[List[AudioInput]] = Field(None, alias="audioInputs")
    file_inputs: Optional[List[FileInput]] = Field(None, alias="fileInputs")
    web_search_enabled: Optional[bool] = Field(False, alias="webSearchEnabled")

    model_config = {"populate_by_name": True}


class PromptLabRequest(BaseModel):
    """Prompt Lab 提示词变体对比请求"""
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    model: str = Field(..., description="模型名称")
    prompts: List[str] = Field(..., min_length=2, max_length=5, description="提示词变体列表（2-5个）")
    image_urls: Optional[List[str]] = Field(None, alias="imageUrls")
    audio_inputs: Optional[List[AudioInput]] = Field(None, alias="audioInputs")
    file_inputs: Optional[List[FileInput]] = Field(None, alias="fileInputs")
    web_search_enabled: Optional[bool] = Field(False, alias="webSearchEnabled")

    model_config = {"populate_by_name": True}


class GenerateVariantsRequest(BaseModel):
    """生成提示词变体请求"""
    prompt: str = Field(..., min_length=1, description="基础提示词")
    count: int = Field(default=3, ge=2, le=5, description="生成变体数量（2-5）")
    model: Optional[str] = Field(default="deepseek/deepseek-chat", description="使用的模型")


class GenerateVariantsResponse(BaseModel):
    """生成提示词变体响应"""
    variants: List[str] = Field(..., description="生成的提示词变体列表")


class StreamChunkVO(BaseModel):
    """SSE 流式响应数据块"""
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    model_name: Optional[str] = Field(None, alias="modelName")
    variant_index: Optional[int] = Field(None, alias="variantIndex")
    content: Optional[str] = Field(None, description="内容片段")
    full_content: Optional[str] = Field(None, alias="fullContent")
    input_tokens: Optional[int] = Field(None, alias="inputTokens")
    output_tokens: Optional[int] = Field(None, alias="outputTokens")
    elapsed_ms: Optional[int] = Field(None, alias="elapsedMs")
    response_time_ms: Optional[int] = Field(None, alias="responseTimeMs")
    cost: Optional[float] = Field(None, description="成本（USD）")
    done: Optional[bool] = Field(None, description="是否完成")
    has_error: Optional[bool] = Field(None, alias="hasError")
    error: Optional[str] = Field(None, description="错误信息")
    reasoning: Optional[str] = Field(None, description="思考过程")
    has_reasoning: Optional[bool] = Field(None, alias="hasReasoning")
    thinking_time: Optional[int] = Field(None, alias="thinkingTime")
    audio_content: Optional[str] = Field(None, alias="audioContent")
    audio_format: Optional[str] = Field(None, alias="audioFormat")
    output_modality: Optional[str] = Field(None, alias="outputModality")

    model_config = {"protected_namespaces": (), "populate_by_name": True}


class VoiceEvalRequest(BaseModel):
    """单模型语音评测请求"""
    model: str = Field(..., description="复合模型 ID platform:vendorId")
    prompt: str = Field("", description="提示词；教师模式 audio_only 时可留空")
    audio_inputs: Optional[List[AudioInput]] = Field(None, alias="audioInputs")
    require_audio_output: bool = Field(False, alias="requireAudioOutput")
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    teacher_mode: bool = Field(False, alias="teacherMode")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt")
    user_message_mode: Optional[str] = Field(None, alias="userMessageMode")

    model_config = {"populate_by_name": True}


class VoiceScoreRequest(BaseModel):
    """单条口语评分（调试 Judge / 听力）"""
    prompt: str = Field("", description="题目描述")
    expected_answer: str = Field(..., alias="expectedAnswer")
    output_content: str = Field("", alias="outputContent")
    output_audio: Optional[str] = Field(None, alias="outputAudio")
    eval_config: Optional[dict] = Field(None, alias="evalConfig")

    model_config = {"populate_by_name": True}
