from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class StudentBase(BaseModel):
    student_id: str
    name: str
    class_id: int


class StudentCreate(StudentBase):
    pass


class StudentImport(BaseModel):
    class_id: int
    students: List[dict]  # [{"student_id": "...", "name": "..."}]


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None


class StudentInDBBase(StudentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class Student(StudentInDBBase):
    pass


class StudentLogin(BaseModel):
    student_id: str
    name: str