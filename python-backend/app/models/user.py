from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from app.db.session import Base


class User(Base):
    """
    用户表模型
    """
    __tablename__ = 'user'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='id')
    user_account = Column('userAccount', String(256), nullable=False, unique=True, comment='账号')
    user_password = Column('userPassword', String(512), nullable=False, comment='密码')
    user_name = Column('userName', String(256), nullable=True, comment='用户昵称')
    user_avatar = Column('userAvatar', String(1024), nullable=True, comment='用户头像')
    user_profile = Column('userProfile', String(512), nullable=True, comment='用户简介')
    user_role = Column('userRole', String(256), nullable=False, default='user', comment='用户角色: user/admin')
    edit_time = Column('editTime', DateTime, nullable=False, default=datetime.now, comment='编辑时间')
    create_time = Column('createTime', DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column('updateTime', DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    is_delete = Column('isDelete', Integer, nullable=False, default=0, comment='是否删除')
