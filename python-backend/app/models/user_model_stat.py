from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, String

from app.db.session import Base


class UserModelStat(Base):
    __tablename__ = 'user_model_stat'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column('userId', BigInteger, nullable=False)
    model_name = Column('modelName', String(100), nullable=False)
    call_count = Column('callCount', BigInteger, nullable=False, default=0)
    total_input_tokens = Column('totalInputTokens', BigInteger, nullable=False, default=0)
    total_output_tokens = Column('totalOutputTokens', BigInteger, nullable=False, default=0)
    total_cost = Column('totalCost', DECIMAL(12, 6), nullable=False, default=Decimal('0'))
    last_used_at = Column('lastUsedAt', DateTime, nullable=True)
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
