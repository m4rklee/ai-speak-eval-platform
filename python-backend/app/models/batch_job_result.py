from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, DECIMAL, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT

from app.db.session import Base


class BatchJobResult(Base):
    __tablename__ = 'batch_job_result'

    id = Column(String(36), primary_key=True)
    job_id = Column('jobId', String(36), nullable=False)
    scenario_item_id = Column('scenarioItemId', String(36), nullable=False)
    model_name = Column('modelName', String(100), nullable=False)
    prompt = Column(Text, nullable=False)
    expected_answer = Column('expectedAnswer', Text, nullable=False)
    output_content = Column('outputContent', Text, nullable=True)
    output_audio = Column('outputAudio', LONGTEXT, nullable=True)
    output_modality = Column('outputModality', String(30), nullable=True)
    status = Column(String(20), nullable=False)
    error_message = Column('errorMessage', String(2000), nullable=True)
    response_time_ms = Column('responseTimeMs', Integer, nullable=True)
    input_tokens = Column('inputTokens', Integer, nullable=True)
    output_tokens = Column('outputTokens', Integer, nullable=True)
    cost = Column(DECIMAL(10, 6), nullable=True)
    score = Column(DECIMAL(5, 2), nullable=True)
    eval_score = Column('evalScore', DECIMAL(5, 2), nullable=True)
    eval_detail = Column('evalDetail', Text, nullable=True)
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
