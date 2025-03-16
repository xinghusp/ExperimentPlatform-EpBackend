from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class JupyterContainer(Base):
    __tablename__ = "jupyter_containers"

    id = Column(BigInteger, primary_key=True, index=True)
    student_task_id = Column(Integer, ForeignKey("student_tasks.id", ondelete="CASCADE"), nullable=False)
    environment_id = Column(BigInteger, ForeignKey("environment_templates.id"), nullable=False)
    container_id = Column(String(200))
    container_name = Column(String(200))
    host = Column(String(100))
    port = Column(Integer)
    status = Column(String(50))
    allow_restart = Column(Boolean, default=True)
    last_active = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    nginx_token = Column(String(32))

    # 关系
    student_task = relationship("StudentTask", back_populates="jupyter_container")
    environment = relationship("EnvironmentTemplate")