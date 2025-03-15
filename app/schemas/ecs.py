from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ECSInstanceBase(BaseModel):
    """ECS实例基础模型"""
    instance_id: Optional[str] = None
    instance_name: Optional[str] = None
    image_id: Optional[str] = None
    instance_type: Optional[str] = None
    cpu: Optional[int] = None
    memory: Optional[int] = None
    bandwidth: Optional[int] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    status: Optional[str] = None
    region_id: Optional[str] = None
    security_group_id: Optional[str] = None
    vswitch_id: Optional[str] = None
    spot_strategy: Optional[str] = None
    cloud_provider: Optional[str] = "aliyun"


class ECSInstanceCreate(ECSInstanceBase):
    """创建ECS实例的请求模型"""
    student_task_id: int
    password: Optional[str] = None


class ECSInstanceUpdate(BaseModel):
    """更新ECS实例的请求模型"""
    instance_id: Optional[str] = None
    instance_name: Optional[str] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    status: Optional[str] = None


class ECSInstanceInDBBase(ECSInstanceBase):
    """数据库中ECS实例的基础模型"""
    id: int
    student_task_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ECSInstance(ECSInstanceInDBBase):
    """API响应中的ECS实例模型"""
    pass