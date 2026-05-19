from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    """
    通用响应包装类
    """
    code: int = Field(default=0, description="响应码，0表示成功")
    data: Optional[T] = Field(default=None, description="响应数据")
    message: str = Field(default="ok", description="响应消息")


class DeleteRequest(BaseModel):
    """
    删除请求
    """
    id: int = Field(..., description="要删除的记录ID", gt=0)
