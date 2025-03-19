from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.schemas.class_ import ClassBase


class TaskBase(BaseModel):
    """任务基础模型"""
    title: str
    description: Optional[str] = None
    max_duration: Optional[int] = None  # 分钟
    max_attempts: Optional[int] = 1
    task_type: Optional[str] = "guacamole"  # 新增字段
    environment_id: Optional[int] = None  # 新增字段


class TaskCreate(TaskBase):
    """创建任务的请求模型"""
    class_ids: List[int]


class TaskUpdate(TaskBase):
    pass


class TaskInDBBase(TaskBase):
    """数据库中任务的基础模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

    class Config:
        orm_mode = True


class Task(TaskInDBBase):
    """API响应中的任务模型"""
    id: int
    classes: List[ClassBase]

    class Config:
        from_attributes = True


class TaskDetail(Task):
    """任务详情模型，包含附件和班级信息"""
    attachments: Optional[List] = []
    classes: Optional[List] = []
    environment: Optional[dict] = None  # 新增字段


class TaskAttachmentBase(BaseModel):
    """任务附件基础模型"""
    file_name: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None




class TaskAttachmentCreate(TaskAttachmentBase):
    """创建任务附件的请求模型"""
    pass


class TaskAttachment(TaskAttachmentBase):
    """API响应中的任务附件模型"""
    id: int
    task_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class TaskWithAttachments(TaskInDBBase):
    """任务详情模型，包含附件（与原API兼容）"""
    attachments: Optional[List[TaskAttachment]] = []
    classes: Optional[List] = []

class StudentTaskBase(BaseModel):
    """学生任务基础模型"""
    student_id: int
    task_id: int
    attempt_number: Optional[int] = 1
    task_type: Optional[str] = "guacamole"  # 新增字段
    status: Optional[str] = "pending"  # 新增字段


class StudentTaskCreate(StudentTaskBase):
    """创建学生任务的请求模型"""
    task_id: int


class StudentTask(StudentTaskBase):
    """API响应中的学生任务模型"""
    id: int
    created_at: datetime
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None

    class Config:
        orm_mode = True


class StudentTaskDetail(StudentTask):
    """学生任务详情，包含任务信息和实例信息"""
    task: Optional[Task] = None
    instance_info: Optional[dict] = None  # 可以是ECS实例或Jupyter容器


class CeleryTaskLogBase(BaseModel):
    """Celery任务日志基础模型"""
    task_id: str
    task_name: str
    status: str
    args: Optional[str] = None
    result: Optional[str] = None
    student_task_id: Optional[int] = None


class CeleryTaskLogCreate(CeleryTaskLogBase):
    """创建Celery任务日志的请求模型"""
    pass


class CeleryTaskLog(CeleryTaskLogBase):
    """API响应中的Celery任务日志模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class StudentTaskResponse(BaseModel):
    id: int
    student_id: int
    student_number: str  # 学号
    student_name: str
    class_name: Optional[str] = None
    task_id: int
    task_name: str
    status: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    duration: Optional[int] = None  # 以秒为单位的持续时间
    attempt_number: int
    task_type: str

    class Config:
        orm_mode = True