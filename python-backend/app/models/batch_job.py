from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, JSON, String, Text

from app.db.session import Base


class BatchJob(Base):
    __tablename__ = 'batch_job'

    id = Column(String(36), primary_key=True)
    user_id = Column('userId', BigInteger, nullable=False)
    scenario_id = Column('scenarioId', String(36), nullable=False)
    models = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    total_tasks = Column('totalTasks', Integer, nullable=False, default=0)
    completed_tasks = Column('completedTasks', Integer, nullable=False, default=0)
    failed_tasks = Column('failedTasks', Integer, nullable=False, default=0)
    concurrency = Column(Integer, nullable=False, default=3)
    output_modality = Column('outputModality', String(30), nullable=False, default='text')
    global_prompt = Column('globalPrompt', Text, nullable=True)
    job_type = Column('jobType', String(30), nullable=False, default='batch_audio')
    system_prompt = Column('systemPrompt', Text, nullable=True)
    user_message_mode = Column('userMessageMode', String(30), nullable=False, default='text_plus_audio')
    eval_config = Column('evalConfig', JSON, nullable=True)
    error_summary = Column('errorSummary', String(1000), nullable=True)
    started_at = Column('startedAt', DateTime, nullable=True)
    finished_at = Column('finishedAt', DateTime, nullable=True)
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now)
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_delete = Column('isDelete', Integer, nullable=False, default=0)
