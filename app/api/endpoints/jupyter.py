import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.crud.jupyter import jupyter_container
from app.crud.environment import environment_template
from app.services import jupyter_service
from app.core.config import settings

router = APIRouter()


@router.get("/containers", response_model=List[schemas.JupyterContainer])
def get_jupyter_containers(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        skip: int = 0,
        limit: int = 100
):
    """管理员获取所有Jupyter容器"""
    return jupyter_container.get_multi(db=db, skip=skip, limit=limit)


@router.get("/active-containers", response_model=List[schemas.JupyterContainer])
def get_active_containers(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        skip: int = 0,
        limit: int = 100
):
    """获取活跃的Jupyter容器"""
    return jupyter_container.get_active_containers(db=db, skip=skip, limit=limit)


@router.get("/containers/{container_id}", response_model=schemas.JupyterContainer)
def get_jupyter_container(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        container_id: int
):
    """获取Jupyter容器详情"""
    container = jupyter_container.get(db=db, id=container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Jupyter container not found")
    return container

