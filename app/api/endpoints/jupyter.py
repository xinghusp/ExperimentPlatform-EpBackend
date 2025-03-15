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


@router.post("/access/{container_id}", response_model=schemas.JupyterAccessInfo)
async def get_jupyter_access_info(
        *,
        db: Session = Depends(deps.get_db),
        current_student: dict = Depends(deps.get_current_student),
        container_id: int,
        response: Response
):
    """获取Jupyter访问信息"""
    # 获取容器信息
    container = jupyter_container.get(db=db, id=container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Jupyter container not found")

    # 检查学生是否有权限访问该容器
    student_task = container.student_task
    if student_task.student_id != current_student["id"]:
        raise HTTPException(status_code=403, detail="You don't have permission to access this container")

    # 检查容器状态
    if container.status != "running":
        raise HTTPException(status_code=400, detail=f"Container is not running (status: {container.status})")

    # 更新容器最后活动时间
    jupyter_container.update_last_active(db=db, id=container_id)

    # 获取访问信息
    access_info = await jupyter_service.get_container_access_info(container_id)
    if not access_info:
        raise HTTPException(status_code=500, detail="Failed to get container access info")

    # 设置Cookie（用于Nginx代理认证）
    token = str(uuid.uuid4())
    response.set_cookie(
        key="jupyter_token",
        value=token,
        domain=settings.COOKIE_DOMAIN,
        path="/",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=1800  # 30分钟
    )

    return schemas.JupyterAccessInfo(
        url=access_info["url"],
        token=access_info["token"]
    )