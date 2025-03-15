from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.crud.ecs import ecs_instance
from app.crud.guacamole import guacamole_connection
router = APIRouter()


@router.get("/instances", response_model=List[schemas.ECSInstance])
def get_ecs_instances(
    *,
    db: Session = Depends(deps.get_db),
    current_admin: dict = Depends(deps.get_current_admin),
    skip: int = 0,
    limit: int = 100
):
    """管理员获取所有ECS实例"""
    return ecs_instance.get_multi(db=db, skip=skip, limit=limit)


@router.get("/active-instances", response_model=List[schemas.ECSInstance])
def get_active_instances(
    *,
    db: Session = Depends(deps.get_db),
    current_admin: dict = Depends(deps.get_current_admin),
    skip: int = 0,
    limit: int = 100
):
    """获取活跃的ECS实例"""
    return ecs_instance.get_active_instances(db=db, skip=skip, limit=limit)


@router.get("/instances/{instance_id}", response_model=schemas.ECSInstance)
def get_ecs_instance(
    *,
    db: Session = Depends(deps.get_db),
    current_admin: dict = Depends(deps.get_current_admin),
    instance_id: int
):
    """获取ECS实例详情"""
    instance = ecs_instance.get(db=db, id=instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="ECS instance not found")
    return instance