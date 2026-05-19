"""
模型信息表模型
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, Integer, String, Text

from app.db.session import Base


class Model(Base):
    __tablename__ = 'model'

    id = Column(String(200), primary_key=True, comment='模型ID platform:vendorId')
    platform = Column(String(20), nullable=False, default='openrouter', comment='平台')
    released_at = Column('releasedAt', DateTime, nullable=True, comment='发布时间')
    model_type = Column('modelType', String(30), nullable=True, comment='模型类型')
    name = Column(String(200), nullable=False, comment='模型显示名称')
    description = Column(Text, nullable=True, comment='模型描述')
    provider = Column(String(100), nullable=True, comment='提供商')
    context_length = Column('contextLength', Integer, nullable=True, comment='上下文长度')
    modality = Column(String(100), nullable=True, comment='模态')
    input_modalities = Column('inputModalities', String(500), nullable=True, comment='输入模态JSON')
    output_modalities = Column('outputModalities', String(500), nullable=True, comment='输出模态JSON')
    input_price = Column('inputPrice', DECIMAL(20, 10), nullable=True, comment='输入价格每百万tokens USD')
    output_price = Column('outputPrice', DECIMAL(20, 10), nullable=True, comment='输出价格每百万tokens USD')
    recommended = Column(Integer, nullable=False, default=0)
    is_china = Column('isChina', Integer, nullable=False, default=0)
    tags = Column(String(500), nullable=True)
    raw_data = Column('rawData', Text, nullable=True)
    total_tokens = Column('totalTokens', BigInteger, nullable=False, default=0)
    total_cost = Column('totalCost', DECIMAL(12, 6), nullable=False, default=Decimal('0'))
    batch_call_count = Column('batchCallCount', BigInteger, nullable=False, default=0)
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
