from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import schemas
from app.api import deps
from app.models.task import Task
from app.crud.environment import environment_template
from app.crud.task import task

router = APIRouter()


@router.post("", response_model=schemas.EnvironmentTemplate)
def create_environment_template(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        env_in: schemas.EnvironmentTemplateCreate
):
    """创建新的环境模板"""
    return environment_template.create_with_admin(
        db=db,
        obj_in=env_in,
        admin_id=current_admin["id"]
    )


@router.get("", response_model=List[schemas.EnvironmentTemplate])
def get_environment_templates(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
):
    """获取环境模板列表，可选按类型过滤"""
    if type:
        return environment_template.get_by_type(db=db, type=type, skip=skip, limit=limit)
    return environment_template.get_multi(db=db, skip=skip, limit=limit)


@router.get("/{template_id}", response_model=schemas.EnvironmentTemplate)
def get_environment_template(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        template_id: int
):
    """获取环境模板详情"""
    template = environment_template.get(db=db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Environment template not found")

    # 获取使用该模板的任务数量
    tasks_count = db.query(func.count(Task.id)).filter(
        Task.environment_id == template_id
    ).scalar()

    # 构造响应
    result = schemas.EnvironmentTemplate.from_orm(template)
    result.tasks_count = tasks_count

    return result


@router.put("/{template_id}", response_model=schemas.EnvironmentTemplate)
def update_environment_template(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        template_id: int,
        env_in: schemas.EnvironmentTemplateUpdate
):
    """更新环境模板"""
    template = environment_template.get(db=db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Environment template not found")

    return environment_template.update(db=db, db_obj=template, obj_in=env_in)


@router.delete("/{template_id}", response_model=schemas.EnvironmentTemplate)
def delete_environment_template(
        *,
        db: Session = Depends(deps.get_db),
        current_admin: dict = Depends(deps.get_current_admin),
        template_id: int
):
    """删除环境模板"""
    template = environment_template.get(db=db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Environment template not found")

    # 检查是否有任务使用此模板
    tasks_using_template = db.query(Task).filter(
        Task.environment_id == template_id
    ).count()

    if tasks_using_template > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete template that is in use by {tasks_using_template} tasks"
        )

    return environment_template.remove(db=db, id=template_id)