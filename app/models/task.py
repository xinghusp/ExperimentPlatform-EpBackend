from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    max_duration = Column(Integer)
    max_attempts = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("administrators.id"), nullable=False)
    task_type = Column(String(50), nullable=False, default="guacamole")
    environment_id = Column(BigInteger, ForeignKey("environment_templates.id"))

    # 关系
    admin = relationship("Administrator")
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete")
    classes = relationship("Class", secondary="task_assignments", back_populates="tasks")
    environment = relationship("EnvironmentTemplate", back_populates="tasks")
    student_tasks = relationship("StudentTask", back_populates="task")


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    task = relationship("Task", back_populates="attachments")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentTask(Base):
    __tablename__ = "student_tasks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    start_at = Column(DateTime)
    end_at = Column(DateTime)
    last_heartbeat = Column(DateTime)
    task_type = Column(String(50), nullable=False, default="guacamole")
    status = Column(String(50), nullable=False, default="pending")

    # 关系
    student = relationship("Student", back_populates="tasks")
    task = relationship("Task", back_populates="student_tasks")
    ecs_instance = relationship("ECSInstance", back_populates="student_task", uselist=False)
    jupyter_container = relationship("JupyterContainer", back_populates="student_task", uselist=False)
    celery_logs = relationship("CeleryTaskLog", back_populates="student_task")


class CeleryTaskLog(Base):
    __tablename__ = "celery_task_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), nullable=False, index=True)
    task_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    args = Column(Text)
    result = Column(Text)
    student_task_id = Column(Integer, ForeignKey("student_tasks.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student_task = relationship("StudentTask", back_populates="celery_logs")