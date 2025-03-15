from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class GuacamoleConnectionBase(BaseModel):
    """Guacamole连接基础模型"""
    connection_id: Optional[str] = None
    connection_name: Optional[str] = None
    protocol: Optional[str] = "rdp"
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    status: Optional[str] = None


class GuacamoleConnectionCreate(GuacamoleConnectionBase):
    """创建Guacamole连接的请求模型"""
    ecs_instance_id: int
    password: Optional[str] = None


class GuacamoleConnectionUpdate(BaseModel):
    """更新Guacamole连接的请求模型"""
    connection_id: Optional[str] = None
    connection_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    status: Optional[str] = None


class GuacamoleConnectionInDBBase(GuacamoleConnectionBase):
    """数据库中Guacamole连接的基础模型"""
    id: int
    ecs_instance_id: int
    created_at: datetime
    last_accessed: Optional[datetime] = None

    class Config:
        orm_mode = True


class GuacamoleConnection(GuacamoleConnectionInDBBase):
    """API响应中的Guacamole连接模型"""
    pass


class GuacamoleCredentials(BaseModel):
    """Guacamole凭据模型，用于客户端连接"""
    connection_id: str
    auth_token: str
    protocol: str