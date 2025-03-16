from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base
from app.models.guacamole import GuacamoleConnection


class ECSInstance(Base):
    __tablename__ = "ecs_instances"

    id = Column(BigInteger, primary_key=True, index=True)
    student_task_id = Column(Integer, ForeignKey("student_tasks.id", ondelete="CASCADE"), nullable=False)
    instance_id = Column(String(100), index=True)
    instance_name = Column(String(200))
    image_id = Column(String(100))
    instance_type = Column(String(100))
    cpu = Column(Integer)
    memory = Column(Integer)
    bandwidth = Column(Integer)
    public_ip = Column(String(50))
    private_ip = Column(String(50))
    status = Column(String(50))
    region_id = Column(String(50))
    security_group_id = Column(String(100))
    vswitch_id = Column(String(100))
    spot_strategy = Column(String(50))
    password = Column(String(255))
    cloud_provider = Column(String(50), default="aliyun")
    auto_release_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student_task = relationship("StudentTask", back_populates="ecs_instance")
    guacamole_connection = relationship("GuacamoleConnection", back_populates="ecs_instance", uselist=False)