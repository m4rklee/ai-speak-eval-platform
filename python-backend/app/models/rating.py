"""
用户评分表模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from app.db.session import Base


class Rating(Base):
    """
    用户评分表
    """
    __tablename__ = 'rating'

    id = Column(String(36), primary_key=True, comment='评分唯一标识')
    conversation_id = Column('conversationId', String(36), nullable=False, comment='对话ID')
    message_index = Column('messageIndex', Integer, nullable=False, comment='消息序号')
    user_id = Column('userId', BigInteger, nullable=False, comment='用户ID')
    rating_type = Column('ratingType', String(20), nullable=False, comment='评分类型')
    winner_model = Column('winnerModel', String(100), nullable=True, comment='获胜模型')
    loser_model = Column('loserModel', String(100), nullable=True, comment='失败模型')
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column(
        'updateTime',
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now
    )
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
