from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin
from app.models.admin import Administrator
from app.crud.admin import admin as crud_admin
from app.schemas.admin import Admin, AdminCreate, AdminUpdate

router = APIRouter()


@router.get("/me", response_model=Admin)
def read_admin_me(
        current_admin: Dict = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    """
    获取当前登录管理员信息
    """
    return current_admin


@router.put("/me", response_model=Admin)
def update_admin_me(
        *,
        db: Session = Depends(get_db),
        current_admin: Dict = Depends(get_current_admin),
        admin_in: AdminUpdate,
):
    """
    更新当前登录管理员信息
    """
    admin = crud_admin.get(db, id=current_admin["id"])
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在"
        )
    admin = crud_admin.update(db, db_obj=admin, obj_in=admin_in)
    return admin


@router.post("/change-password", response_model=Dict[str, str])
def change_password(
        *,
        db: Session = Depends(get_db),
        current_admin: Dict = Depends(get_current_admin),
        current_password: str,
        new_password: str,
):
    """
    更改管理员密码
    """
    admin = crud_admin.get(db, id=current_admin["id"])
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在"
        )

    # 验证当前密码
    admin_authenticated = crud_admin.authenticate(
        db, username=admin.username, password=current_password
    )
    if not admin_authenticated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确"
        )

    # 更新密码
    crud_admin.update_password(db, db_obj=admin, new_password=new_password)
    return {"message": "密码已更新"}


@router.get("/", response_model=List[Admin])
def list_admins(
        db: Session = Depends(get_db),
        current_admin: Dict = Depends(get_current_admin),
        skip: int = 0,
        limit: int = 100,
):
    """
    获取管理员列表 (仅超级管理员可访问)
    """
    # 检查是否为超级管理员
    if current_admin.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )

    admins = crud_admin.get_multi(db, skip=skip, limit=limit)
    return admins


@router.post("/", response_model=Admin)
def create_admin(
        *,
        db: Session = Depends(get_db),
        current_admin: Dict = Depends(get_current_admin),
        admin_in: AdminCreate
):
    """
    创建新管理员 (仅超级管理员可访问)
    """
    # 检查是否为超级管理员
    if current_admin.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )

    # 检查用户名是否已存在
    admin = crud_admin.get_by_username(db, username=admin_in.username)
    if admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    admin = crud_admin.create(db, obj_in=admin_in)
    return admin