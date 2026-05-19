from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class NormalizedModel:
    platform: str
    vendor_id: str
    name: str
    description: Optional[str] = None
    provider: Optional[str] = None
    context_length: Optional[int] = None
    modality: Optional[str] = None
    input_modalities: list[str] = field(default_factory=list)
    output_modalities: list[str] = field(default_factory=list)
    input_price: Optional[Decimal] = None  # per million tokens USD
    output_price: Optional[Decimal] = None
    released_at: Optional[datetime] = None
    model_type: Optional[str] = None
    recommended: int = 0
    is_china: int = 0
    raw_data: Optional[str] = None

    @property
    def composite_id(self) -> str:
        return f"{self.platform}:{self.vendor_id}"


@dataclass
class ChatResult:
    text: str = ""
    audio_data: Optional[str] = None
    audio_format: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    raw_message: Optional[Any] = None


class ModelProvider(ABC):
    platform: str

    @abstractmethod
    async def fetch_models(self) -> list[NormalizedModel]:
        ...

    @abstractmethod
    async def chat_completion(
        self,
        vendor_model_id: str,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        require_audio_output: bool = False,
        timeout: float = 120.0,
    ) -> ChatResult:
        ...

    async def chat_completion_stream(self, vendor_model_id: str, messages: list[dict[str, Any]], **kwargs):
        raise NotImplementedError
