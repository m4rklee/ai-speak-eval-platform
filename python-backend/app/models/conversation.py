"""
对话记录表模型
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, Integer, JSON, String

from app.db.session import Base


class Conversation(Base):
    """
    对话记录表模型
    """
    __tablename__ = 'conversation'

    id = Column(String(36), primary_key=True, comment='对话唯一标识')
    user_id = Column('userId', BigInteger, nullable=False, comment='用户ID')
    title = Column(String(200), nullable=True, comment='对话标题')
    conversation_type = Column(
        'conversationType',
        String(20),
        nullable=False,
        comment='对话类型: side_by_side/prompt_lab/battle'
    )
    models = Column(JSON, nullable=False, comment='参与的模型列表')
    code_preview_enabled = Column(
        'codePreviewEnabled',
        Integer,
        nullable=False,
        default=0,
        comment='是否启用代码预览'
    )
    total_tokens = Column('totalTokens', Integer, nullable=True, default=0)
    total_cost = Column('totalCost', DECIMAL(10, 4), nullable=True, default=Decimal('0'))
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column(
        'updateTime',
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now
    )
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
