import datetime
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app import schemas
from app.api import deps
from app.core.config import settings
from app.core.security import create_access_token
from app.services import ecs_service, jupyter_service
from app.crud.task import student_task
from app.crud.task import task
from app.crud.ecs import ecs_instance
from app.crud.guacamole import guacamole_connection
from app.crud.jupyter import jupyter_container
from app.crud.environment import environment_template
from app.services.ali_cloud import ali_cloud_service
from app.services.guacamole import guacamole_service
from fastapi import Response
router = APIRouter()


@router.get("/tasks", response_model=List[Dict[str, Any]])
def get_student_tasks(
        *,
        db: Session = Depends(deps.get_db),
        current_student: Dict = Depends(deps.get_current_student),
        skip: int = 0,
        limit: int = 100,
):
    """
    获取学生的任务列表
    """
    tasks_data = task.get_tasks_for_student(db, student_id=current_student["id"], skip=skip, limit=limit)
    return tasks_data


@router.post("/start-experiment/{task_id}", response_model=Dict[str, Any])
async def start_experiment(
        *,
        db: Session = Depends(deps.get_db),
        current_student: Dict = Depends(deps.get_current_student),
        task_id: int,
):
    """
    开始实验
    """
    # 获取任务信息
    task_data = task.get(db, id=task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    # 检查学生是否有权限访问该任务
    student_id = current_student["id"]

    # 检查学生实验次数是否超限
    latest_student_task = student_task.get_latest_for_student_task(db, student_id=student_id, task_id=task_id)
    attempt_number = 1
    if latest_student_task:
        attempt_number = latest_student_task.attempt_number + 1
        # 检查是否超过最大尝试次数
        if attempt_number > task_data.max_attempts:
            raise HTTPException(status_code=400, detail="You have reached the maximum allowed attempts for this task")

    # 创建学生任务记录
    new_student_task = student_task.create_student_task(
        db,
        student_id=student_id,
        task_id=task_id,
        task_type=task_data.task_type,
        attempt_number=attempt_number
    )

    # 根据任务类型执行不同的实验启动流程
    result = {"student_task_id": new_student_task.id}

    if task_data.task_type == "guacamole":
        # 启动ECS实例
        ecs_data = await start_ecs_instance(db, task_data, new_student_task.id)
        result.update(ecs_data)
    elif task_data.task_type == "jupyter":
        # 启动Jupyter容器
        jupyter_data = await start_jupyter_container(db, task_data, new_student_task.id)
        result.update(jupyter_data)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported task type: {task_data.task_type}")

    return result


@router.post("/stop-experiment/{student_task_id}")
async def stop_experiment(
        *,
        db: Session = Depends(deps.get_db),
        current_student: Dict = Depends(deps.get_current_student),
        student_task_id: int,
):
    """
    停止实验
    """
    # 获取学生任务
    student_task_obj = student_task.get(db, id=student_task_id)
    if not student_task_obj or student_task_obj.student_id != current_student["id"]:
        raise HTTPException(status_code=404, detail="Student task not found")

    # 根据任务类型执行不同的停止流程
    if student_task_obj.task_type == "guacamole":
        # 停止ECS实例
        ecs = ecs_instance.get_by_student_task_id(db, student_task_id=student_task_id)
        if ecs and ecs.instance_id:
            await ecs_service.stop_instance(ecs.instance_id)
            #ecs_instance.update_status(db, instance_id=ecs.instance_id, status="Stopped")

    elif student_task_obj.task_type == "jupyter":
        # 停止Jupyter容器
        jupyter = jupyter_container.get_by_student_task_id(db, student_task_id=student_task_id)
        if jupyter and jupyter.container_id:
            await jupyter_service.stop_container(jupyter.container_id)
            jupyter_container.update_status(db, id=jupyter.id, status="Stopped")

    # 结束学生任务
    student_task.end_experiment(db, student_task_id=student_task_id)

    return {"message": "Experiment stopped successfully"}


@router.post("/heartbeat/{student_task_id}")
def update_heartbeat(
        *,
        db: Session = Depends(deps.get_db),
        current_student: Dict = Depends(deps.get_current_student),
        student_task_id: int,
):
    """
    更新实验心跳
    """
    # 获取学生任务
    student_task_obj = student_task.get(db, id=student_task_id)
    if not student_task_obj or student_task_obj.student_id != current_student["id"]:
        raise HTTPException(status_code=404, detail="Student task not found")

    # 更新心跳
    student_task.update_heartbeat(db, student_task_id=student_task_id)

    # 根据任务类型更新不同环境的最后活动时间
    if student_task_obj.task_type == "guacamole":
        # 更新Guacamole连接的最后访问时间
        ecs = ecs_instance.get_by_student_task_id(db, student_task_id=student_task_id)
        if ecs:
            conn = guacamole_connection.get_by_ecs_instance_id(db, ecs_instance_id=ecs.id)
            if conn:
                guacamole_connection.update_last_accessed(db, id=conn.id)

    elif student_task_obj.task_type == "jupyter":
        # 更新Jupyter容器的最后活动时间
        jupyter = jupyter_container.get_by_student_task_id(db, student_task_id=student_task_id)
        if jupyter:
            jupyter_container.update_last_active(db, id=jupyter.id)

    return {"message": "Heartbeat updated"}


@router.get("/{student_task_id}", response_model=schemas.StudentTaskDetail)
def get_student_task_detail(
        *,
        db: Session = Depends(deps.get_db),
        current_student: Dict = Depends(deps.get_current_student),
        student_task_id: int,
):
    """
    获取学生任务详情
    """
    # 获取学生任务详情
    result = student_task.get_task_with_environment_detail(db, student_task_id=student_task_id)
    if not result or result["student_task"]["student_id"] != current_student["id"]:
        raise HTTPException(status_code=404, detail="Student task not found")

    return result

@router.get("/{student_task_id}/guacamole-token", response_model=Dict[str, str])
def generate_guacamole_token(
        student_task_id: int,
        db: Session = Depends(deps.get_db),
        current_student: Dict = Depends(deps.get_current_student)
):
    """
    生成临时的Guacamole访问令牌
    """
    # 验证学生任务存在且属于当前学生
    student_task_obj = student_task.get(db, id=student_task_id)

    if not student_task_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    token_data = {
        "sub":  f"st_{student_task_id}",
        "role": "student"  # 角色信息
    }

    # 生成临时令牌 (30分钟有效)
    temp_token = create_access_token(token_data,
        expires_delta=datetime.timedelta(minutes=30)
    )

    return {"token": temp_token}

@router.get("/{student_task_id}/jupyter-token", response_model=schemas.JupyterAccessInfo)
async def get_jupyter_access_info(
        *,
        db: Session = Depends(deps.get_db),
        current_student: dict = Depends(deps.get_current_student),
        student_task_id: int,
        response: Response
):
    """获取Jupyter访问信息"""
    # 获取容器信息
    container = jupyter_container.get_by_student_task_id(db=db,student_task_id=student_task_id)
    if not container:
        raise HTTPException(status_code=404, detail="Jupyter container not found")

    # 检查学生是否有权限访问该容器
    student_task_model = container.student_task
    if student_task_model.student_id != current_student["id"]:
        raise HTTPException(status_code=403, detail="You don't have permission to access this container")

    # 检查容器状态
    if container.status != "Running":
        raise HTTPException(status_code=400, detail=f"Container is not running (status: {container.status})")

    if not container.nginx_token or container.nginx_token.strip()=='':
        raise HTTPException(status_code=400, detail="Jupyter has not ready for nginx accessing")

    # 更新容器最后活动时间
    jupyter_container.update_last_active(db=db, id=container.container_id)


    # 设置Cookie（用于Nginx代理认证）

    response.set_cookie(
        key="jupyter_token",
        value=container.nginx_token,
        domain=settings.JUPYTER_COOKIE_DOMAIN,
        path="/",
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=1800
    )

    return schemas.JupyterAccessInfo(
        url=f"http://{settings.JUPYTER_COOKIE_DOMAIN}",
        port=str(container.port),
        token=container.nginx_token
    )

# 辅助函数: 启动ECS实例
async def start_ecs_instance(db: Session, task_data, student_task_id: int):
    """启动ECS实例并创建相关记录"""
    # 获取环境模板
    env = environment_template.get(db, id=task_data.environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment template not found")
    print("config:",env.resource_config)
    # 创建ECS实例
    instance_result = await ecs_service.create_instance(
        task_id=task_data.id,
        student_task_id=student_task_id
    )

    # 创建ECS实例记录
    ecs = ecs_instance.create(
        db,
        obj_in=schemas.ECSInstanceCreate(
            student_task_id=student_task_id,
            instance_id=None,
            instance_name=instance_result["instance_name"],
            image_id=env.image,
            instance_type=env.resource_config.get("instance_type","cn-hangzhou"),
            status="Creating",
            region_id=env.resource_config.get("region_id", None),
            security_group_id=env.resource_config.get("security_group_id", None),
            vswitch_id=env.resource_config.get("vswitch_id", None),
            spot_strategy=env.resource_config.get("spot_strategy", None),
            password=env.resource_config.get("password")
        )
    )

    # 更新学生任务状态
    student_task.update_status(db, student_task_id=student_task_id, status="creating")

    return {
        "message": "ECS instance creation started",
        "instance_id": None,
        "instance_name": instance_result["instance_name"]

    }


# 辅助函数: 启动Jupyter容器
async def start_jupyter_container(db: Session, task_data, student_task_id: int):
    """启动Jupyter容器并创建相关记录"""
    # 获取环境模板
    env = environment_template.get(db, id=task_data.environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment template not found")

    # 创建Jupyter容器记录
    container = jupyter_container.create(
        db,
        obj_in=schemas.JupyterContainerCreate(
            student_task_id=student_task_id,
            environment_id=env.id,
            status="creating"
        )
    )

    # 更新学生任务状态
    student_task.update_status(db, student_task_id=student_task_id, status="creating")

    # 启动容器（异步任务）
    await jupyter_service.create_container(container.id, env.image, env.resource_config)

    return {
        "message": "Jupyter container creation started",
        "container_id": container.id
    }