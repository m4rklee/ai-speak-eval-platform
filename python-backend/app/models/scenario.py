from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from app.db.session import Base


class Scenario(Base):
    __tablename__ = 'scenario'

    id = Column(String(36), primary_key=True)
    user_id = Column('userId', BigInteger, nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    source_type = Column('sourceType', String(20), nullable=False)
    category = Column(String(100), nullable=True)
    item_count = Column('itemCount', Integer, nullable=False, default=0)
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
