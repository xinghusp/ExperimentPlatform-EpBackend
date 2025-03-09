from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AdminBase(BaseModel):
    username: str


class AdminCreate(AdminBase):
    password: str

class AdminUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None

class AdminInDBBase(AdminBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,  # 替代原来的 orm_mode = True
    }


class Admin(AdminInDBBase):
    pass


class AdminInDB(AdminInDBBase):
    password: str

from pydantic import BaseModel

class AdminLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    user_id: int