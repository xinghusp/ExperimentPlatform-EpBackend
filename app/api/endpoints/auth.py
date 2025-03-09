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
    payload = {"sub": str(admin.id), "role": "admin"}

    return {
        "access_token": create_access_token(
            payload, expires_delta=access_token_expires
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
    payload = {"sub": str(student.id), "role": "student"}
    
    return {
        "access_token": create_access_token(
            payload, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user_id": student.id,
        "student_id": student.student_id,
        "name": student.name,
        "role": "student"
    }


@router.post("/admin/register", response_model=Admin)
def register_admin(
    admin_in: AdminCreate, db: Session = Depends(get_db)
):
    """
    管理员注册 (初始管理员创建时使用)
    """
    admin = crud_admin.create(db, obj_in=admin_in)
    return admin