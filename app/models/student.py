from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
import datetime

from app.db.base import Base


class Student(Base):
    """学生表"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    class_id = Column(Integer, ForeignKey("classes.id"))

    # 添加与班级的关系
    class_ = relationship("Class", back_populates="students")

    # 添加与任务的关系
    # 1. 直接通过班级获取任务（多对多关系）
    tasks = relationship(
        "Task",
        secondary="task_assignments",
        primaryjoin="Student.class_id == Class.id",
        secondaryjoin="and_(TaskAssignment.class_id == Class.id, TaskAssignment.task_id == Task.id)",
        viewonly=True
    )

    # 2. 学生的任务执行记录
    student_tasks = relationship("StudentTask", back_populates="student", cascade="all, delete-orphan")