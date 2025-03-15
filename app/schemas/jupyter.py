from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class JupyterContainerBase(BaseModel):
    """Jupyter容器基础模型"""
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    status: Optional[str] = "pending"
    allow_restart: Optional[bool] = True


class JupyterContainerCreate(JupyterContainerBase):
    """创建Jupyter容器的请求模型"""
    student_task_id: int
    environment_id: int


class JupyterContainerUpdate(BaseModel):
    """更新Jupyter容器的请求模型"""
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    status: Optional[str] = None
    allow_restart: Optional[bool] = None


class JupyterContainerInDBBase(JupyterContainerBase):
    """数据库中Jupyter容器的基础模型"""
    id: int
    student_task_id: int
    environment_id: int
    created_at: datetime
    last_active: Optional[datetime] = None

    class Config:
        orm_mode = True


class JupyterContainer(JupyterContainerInDBBase):
    """API响应中的Jupyter容器模型"""
    pass


class JupyterSessionInfo(BaseModel):
    """Jupyter会话信息"""
    container_id: str
    url: str
    token: str
    student_id: int


class JupyterAccessInfo(BaseModel):
    """提供给前端的Jupyter访问信息"""
    url: str
    token: str