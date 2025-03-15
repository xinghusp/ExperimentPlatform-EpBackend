from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class EnvironmentTemplate(Base):
    __tablename__ = "environment_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, index=True)
    image = Column(Text, nullable=False)
    resource_config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("administrators.id"))

    # 关系
    tasks = relationship("Task", back_populates="environment")
    admin = relationship("Administrator")