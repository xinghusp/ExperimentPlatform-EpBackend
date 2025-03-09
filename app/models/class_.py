from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
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
    students = relationship("Student", back_populates="class_")
    task_assignments = relationship("TaskAssignment", back_populates="class_")
    tasks  = relationship("Task", secondary="task_assignments", back_populates="classes")