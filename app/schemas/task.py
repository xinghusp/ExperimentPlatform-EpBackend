from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import json

from app.schemas.class_ import Class


class TaskAttachmentBase(BaseModel):
    file_name: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None


class TaskAttachmentCreate(TaskAttachmentBase):
    pass


class TaskAttachmentInDBBase(TaskAttachmentBase):
    id: int
    task_id: int
    created_at: datetime

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class TaskAttachment(TaskAttachmentInDBBase):
    pass


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    max_duration: Optional[int] = None
    max_attempts: int
    image_id: str
    region_id: str
    instance_type: str
    security_group_id: str
    vswitch_id: str
    internet_max_bandwidth_out: int
    spot_strategy: str
    password: str
    custom_params: Optional[Dict[str, Any]] = None


class TaskCreate(TaskBase):
    class_ids: List[int]


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    max_duration: Optional[int] = None
    max_attempts: Optional[int] = None
    image_id: Optional[str] = None
    region_id: Optional[str] = None
    instance_type: Optional[str] = None
    security_group_id: Optional[str] = None
    vswitch_id: Optional[str] = None
    internet_max_bandwidth_out: Optional[int] = None
    spot_strategy: Optional[str] = None
    password: Optional[str] = None
    custom_params: Optional[Dict[str, Any]] = None
    class_ids: Optional[List[int]] = None


class TaskInDBBase(TaskBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    max_duration: Optional[int] = None
    max_attempts: int = 1
    region_id: str
    image_id: str
    instance_type: str
    security_group_id: str
    vswitch_id: str
    internet_max_bandwidth_out: int
    spot_strategy: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    classes: List[Class] = []
    password: str

    class Config:
        orm_mode = True


class TaskWithAttachments(Task):
    attachments: List[TaskAttachment] = []


class StudentTaskBase(BaseModel):
    student_id: int
    task_id: int
    ecs_instance_id: Optional[str] = None
    ecs_instance_status: Optional[str] = None
    ecs_ip_address: Optional[str] = None
    attempt_number: int = 1
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    auto_release_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None


class StudentTaskCreate(BaseModel):
    task_id: int


class StudentTaskInDBBase(StudentTaskBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class StudentTask(StudentTaskInDBBase):
    pass


class StudentTaskDetail(StudentTask):
    task: Task
    remaining_time: Optional[int] = None  # 剩余时间（分钟）


class CeleryTaskLogBase(BaseModel):
    task_id: str
    task_name: str
    status: str
    args: Optional[str] = None
    result: Optional[str] = None
    student_task_id: Optional[int] = None


class CeleryTaskLogCreate(CeleryTaskLogBase):
    pass


class CeleryTaskLogInDBBase(CeleryTaskLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class CeleryTaskLog(CeleryTaskLogInDBBase):
    pass