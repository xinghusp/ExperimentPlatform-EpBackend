from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Text, JSON, text
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.admin import Administrator

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    max_duration = Column(Integer, nullable=True)  # 最大实验时长(分钟)
    max_attempts = Column(Integer, nullable=False, default=1)  # 最大实验次数
    image_id = Column(String(100), nullable=False)  # 阿里云镜像ID
    region_id = Column(String(50), nullable=False)  # 阿里云区域ID
    instance_type = Column(String(50), nullable=False)  # ECS实例类型
    security_group_id = Column(String(100), nullable=False)  # 安全组ID
    vswitch_id = Column(String(100), nullable=False)  # 交换机ID
    internet_max_bandwidth_out = Column(Integer, nullable=False)  # 最大出网带宽
    spot_strategy = Column(String(50), nullable=False)  # 竞价策略
    password = Column(String(255), nullable=False)  # ECS密码
    custom_params = Column(JSON, nullable=True)  # ECS自定义参数，JSON格式
    created_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        nullable=False
    )
    created_by = Column(Integer, ForeignKey("administrators.id"), nullable=False)
    
    # Relationships
    admin = relationship("Administrator")
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete-orphan")
    task_assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    student_tasks = relationship("StudentTask", back_populates="task")
    classes = relationship("Class", secondary="task_assignments", back_populates="tasks")


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(50), nullable=True)
    created_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    
    # Relationships
    task = relationship("Task", back_populates="attachments")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    created_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    
    # Relationships
    task = relationship("Task", back_populates="task_assignments")
    class_ = relationship("Class", back_populates="task_assignments")


class StudentTask(Base):
    __tablename__ = "student_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    ecs_instance_id = Column(String(100), nullable=True)
    ecs_instance_status = Column(String(50), nullable=True)
    ecs_ip_address = Column(String(50), nullable=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    created_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    start_at = Column(TIMESTAMP, nullable=True)
    end_at = Column(TIMESTAMP, nullable=True)
    auto_release_time = Column(TIMESTAMP, nullable=True)
    last_heartbeat = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="student_tasks")
    task = relationship("Task", back_populates="student_tasks")
    celery_logs = relationship("CeleryTaskLog", back_populates="student_task")


class CeleryTaskLog(Base):
    __tablename__ = "celery_task_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String(100), nullable=False)
    task_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    args = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    student_task_id = Column(Integer, ForeignKey("student_tasks.id"), nullable=True)
    created_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP, 
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        nullable=False
    )
    
    # Relationships
    student_task = relationship("StudentTask", back_populates="celery_logs")