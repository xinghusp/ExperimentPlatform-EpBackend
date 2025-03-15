from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# 导入所有模型，以便Alembic可以检测和生成迁移脚本

from app.db.base_class import Base  # noqa
from app.models.admin import Administrator  # noqa
from app.models.class_ import Class  # noqa
from app.models.student import Student  # noqa
from app.models.task import Task, TaskAttachment, TaskAssignment, StudentTask, CeleryTaskLog  # noqa
from app.models.environment import EnvironmentTemplate  # noqa
from app.models.ecs import ECSInstance  # noqa
from app.models.guacamole import GuacamoleConnection  # noqa
from app.models.jupyter import JupyterContainer  # noqa

from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=200,       # 允许的最大连接数
    max_overflow=200,    # 允许的额外溢出连接数
    pool_timeout=30,    # 连接池超时时间
    pool_recycle=1800   # 连接回收时间，避免长时间未使用的连接失效
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()