"""
对话消息表模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, Integer, String, Text

from app.db.session import Base


class ConversationMessage(Base):
    """
    对话消息表模型
    """
    __tablename__ = 'conversation_message'

    id = Column(String(36), primary_key=True, comment='消息唯一标识')
    conversation_id = Column('conversationId', String(36), nullable=False, comment='对话ID')
    user_id = Column('userId', BigInteger, nullable=False, comment='用户ID')
    message_index = Column('messageIndex', Integer, nullable=False, comment='消息序号')
    role = Column(String(20), nullable=False, comment='角色: user/assistant')
    model_name = Column('modelName', String(100), nullable=True, comment='模型名称')
    content = Column(Text, nullable=False, comment='消息内容')
    response_time_ms = Column('responseTimeMs', Integer, nullable=True, comment='响应时间')
    input_tokens = Column('inputTokens', Integer, nullable=True, comment='输入Token数')
    output_tokens = Column('outputTokens', Integer, nullable=True, comment='输出Token数')
    cost = Column(DECIMAL(10, 6), nullable=True, comment='成本')
    reasoning = Column(Text, nullable=True, comment='思考过程')
    output_audio = Column('outputAudio', Text, nullable=True, comment='输出音频JSON')
    output_modality = Column('outputModality', String(30), nullable=True, comment='输出模态')
    code_blocks = Column('codeBlocks', Text, nullable=True, comment='代码块列表')
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column(
        'updateTime',
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now
    )
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
