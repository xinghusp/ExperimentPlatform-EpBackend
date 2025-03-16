from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel


class ResourceConfig(BaseModel):
    """资源配置模型"""
    cpu: Optional[str] = None  # 如 "500m", "1"
    memory: Optional[str] = None  # 如 "1Gi", "512Mi"
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    disk_size: Optional[str] = None  # 如 "10Gi"
    bandwidth: Optional[int] = None  # 带宽 Mbps

    # ECS特有参数
    instance_type: Optional[str] = None  # 如 "ecs.t6-c1m1.large"
    security_group_id: Optional[str] = None
    vswitch_id: Optional[str] = None
    spot_strategy: Optional[str] = None


class EnvironmentTemplateBase(BaseModel):
    """环境模板基础模型"""
    name: str
    description: Optional[str] = None
    type: str  # 环境类型："guacamole", "jupyter" 等
    image: str  # 镜像ID或Docker镜像名
    resource_config: Optional[Dict[str, Any]] = None


class EnvironmentTemplateCreate(EnvironmentTemplateBase):
    """创建环境模板的请求模型"""
    pass


class EnvironmentTemplateUpdate(BaseModel):
    """更新环境模板的请求模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    image: Optional[str] = None
    resource_config: Optional[Dict[str, Any]] = None


class EnvironmentTemplateInDBBase(EnvironmentTemplateBase):
    """数据库中环境模板的基础模型"""
    id: int
    created_at: datetime
    created_by: int

    class Config:
        orm_mode = True


class EnvironmentTemplate(EnvironmentTemplateInDBBase):
    """API响应中的环境模板模型"""
    pass


class EnvironmentTemplateDetail(EnvironmentTemplate):
    """包含更多细节的环境模板模型"""
    tasks_count: Optional[int] = 0
    class Config:
        from_attributes = True