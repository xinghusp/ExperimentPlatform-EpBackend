from pydantic import BaseModel
from typing import Optional, List, ClassVar
from datetime import datetime

from sqlalchemy.orm import relationship


class ClassBase(BaseModel):
    name: str
    description: Optional[str] = None


class ClassCreate(ClassBase):
    pass


class ClassUpdate(ClassBase):
    pass


class ClassInDBBase(ClassBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class Class(ClassInDBBase):
    pass


class ClassWithCount(Class):
    student_count: int