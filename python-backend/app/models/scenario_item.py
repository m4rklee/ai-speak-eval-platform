from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.session import Base


class ScenarioItem(Base):
    __tablename__ = 'scenario_item'

    id = Column(String(36), primary_key=True)
    scenario_id = Column('scenarioId', String(36), nullable=False)
    prompt = Column(Text, nullable=False)
    expected_answer = Column('expectedAnswer', Text, nullable=False)
    model_output = Column('modelOutput', Text, nullable=True)
    category = Column(String(100), nullable=True)
    input_type = Column('inputType', String(20), nullable=False, default='text')
    audio_data = Column('audioData', Text, nullable=True)
    audio_format = Column('audioFormat', String(20), nullable=True)
    audio_file_name = Column('audioFileName', String(255), nullable=True)
    sort_order = Column('sortOrder', Integer, nullable=False, default=0)
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
