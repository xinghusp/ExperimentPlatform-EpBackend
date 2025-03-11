from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.admin import AdminCreate, Admin, AdminLogin, Token
from app.schemas.student import StudentLogin
from app.crud.admin import admin as crud_admin
from app.crud.student import student as crud_student

router = APIRouter()


@router.post("/admin/login", response_model=Token)
def login_admin_access_token(form_data: AdminLogin, db: Session = Depends(get_db)
                             ):
    """
    管理员登录获取访问令牌
    """
    admin = crud_admin.authenticate(
        db, username=form_data.username, password=form_data.password
    )
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 创建简化的载荷，不再嵌套JSON字符串
    token_data = {
        "sub": str(admin.id),  # sub字段直接是用户ID
        "role": "admin"  # 角色信息
    }

    return {
        "access_token": create_access_token(
            token_data, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user_id": admin.id,
        "username": admin.username,
        "role": "admin"
    }


@router.post("/student/login", response_model=dict)
def login_student_access_token(student_login: StudentLogin, db: Session = Depends(get_db)):
    """
    学生登录获取访问令牌
    """
    student = crud_student.authenticate(
        db, student_id=student_login.student_id, name=student_login.name
    )
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="学号或姓名错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 创建简化的载荷，不再嵌套JSON字符串
    token_data = {
        "sub": str(student.id),  # sub字段直接是用户ID
        "role": "student"  # 角色信息
    }

    return {
        "access_token": create_access_token(
            token_data, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user_id": student.id,
        "student_id": student.student_id,
        "name": student.name,
        "role": "student"
    }
