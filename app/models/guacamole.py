from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class GuacamoleConnection(Base):
    __tablename__ = "guacamole_connections"

    id = Column(BigInteger, primary_key=True, index=True)
    ecs_instance_id = Column(BigInteger, ForeignKey("ecs_instances.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(String(100))
    connection_name = Column(String(200))
    protocol = Column(String(20), default="rdp")
    host = Column(String(100))
    port = Column(Integer)
    username = Column(String(100))
    password = Column(String(255))
    status = Column(String(50))
    last_accessed = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    ecs_instance = relationship("ECSInstance", back_populates="guacamole_connection")