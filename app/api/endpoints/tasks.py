from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import json
import shutil
import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_admin, get_current_student
from app.core.config import settings
from app.core.security import create_access_token
from app.models.class_ import Class
from app.models.student import Student
from app.models.ecs import ECSInstance as ECSInstanceDb
from app.schemas.class_ import ClassInDBBase
from app.schemas.task import TaskCreate, TaskUpdate, Task, TaskWithAttachments, TaskAttachmentCreate, StudentTaskCreate, \
    StudentTask
from app.crud.task import task as crud_task
from app.crud.task import student_task as crud_student_task
from app.crud.environment import environment_template
from app.tasks.ecs_tasks import create_ecs_instance, delete_instance
from app.models.task import Task as TaskDb, TaskAttachment as TaskAttachmentDb, StudentTask as StudentTaskDb, \
    TaskAssignment as TaskAssDb
from app.models.class_ import Class as ClassDb
from app.models.student import Student as StudentDb
from app.schemas.ecs import ECSInstance

router = APIRouter()


@router.post("/", response_model=Task)
async def create_task(
        title: str = Form(...),
        description: str = Form(None),
        max_duration: int = Form(None),
        max_attempts: int = Form(...),
        class_ids: str = Form(...),
        task_type: str = Form("guacamole"),  # 新增: 默认为guacamole类型
        environment_id: int = Form(...),  # 新增: 环境模板ID
        files: List[UploadFile] = File(None),
        db: Session = Depends(get_db),
        current_admin: dict = Depends(get_current_admin)
):
    """
    创建任务
    """
    # 解析表单数据
    task_data = {"title": title, "description": description, "max_duration": max_duration, "max_attempts": max_attempts,
                 "class_ids": json.loads(class_ids), "task_type": task_type, "environment_id": environment_id}


    # 创建任务
    task_in = TaskCreate(**task_data)
    task_obj = crud_task.create_with_admin(db=db, obj_in=task_in, admin_id=current_admin["id"])

    # 处理上传的附件
    if files:
        upload_dir = os.path.join(settings.UPLOAD_FOLDER, f"task_{task_obj.id}")
        os.makedirs(upload_dir, exist_ok=True)

        for file in files:
            if not file.filename:
                continue

            file_path = os.path.join(upload_dir, file.filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 创建附件记录
            attachment_in = TaskAttachmentCreate(
                file_name=file.filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                file_type=file.content_type
            )
            crud_task.create_attachment(db=db, obj_in=attachment_in, task_id=task_obj.id)

    return task_obj


@router.get("/")
def read_tasks(
        task_type: str=None,
        db: Session = Depends(get_db),
        current_admin=Depends(get_current_admin)
):
    """
    获取所有任务列表，包括关联的班级信息
    """
    # 使用joinedload预加载关联的班级信息
    if task_type is None:
        tasks = db.query(TaskDb).options(
            joinedload(TaskDb.classes)
        ).all()
    else:
        tasks = db.query(TaskDb).filter(TaskDb.task_type==task_type).options(
        joinedload(TaskDb.classes)
    ).all()

    # 如果需要手动处理关联关系，可以使用下面的代码
    if not tasks:
        return []

    # 构建带有班级信息的任务列表
    result = []
    for task in tasks:
        # 基本任务信息
        task_dict = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "max_duration": task.max_duration,
            "max_attempts": task.max_attempts,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "task_type": task.task_type,  # 新增字段
            "environment_id": task.environment_id,  # 新增字段
            "classes": []
        }

        # 获取环境信息
        if task.environment_id:
            env = environment_template.get(db, id=task.environment_id)
            if env:
                task_dict["environment"] = {
                    "id": env.id,
                    "name": env.name,
                    "type": env.type,
                    "image": env.image,
                }

                # 针对guacamole类型，保留旧字段以兼容
                if env.type == "guacamole" and env.resource_config:
                    task_dict["instance_type"] = env.resource_config.get("instance_type")
                    task_dict["region_id"] = env.resource_config.get("region_id")
                    task_dict["image_id"] = env.image
                    task_dict["security_group_id"] = env.resource_config.get("security_group_id")
                    task_dict["vswitch_id"] = env.resource_config.get("vswitch_id")
                    task_dict["internet_max_bandwidth_out"] = env.resource_config.get("bandwidth")
                    task_dict["spot_strategy"] = env.resource_config.get("spot_strategy")

        # 查询关联的班级信息
        class_tasks = db.query(TaskAssDb).filter(TaskAssDb.task_id == task.id).all()
        class_ids = [ct.class_id for ct in class_tasks]

        if class_ids:
            classes = db.query(ClassDb).filter(ClassDb.id.in_(class_ids)).all()
            task_dict["classes"] = [{"id": c.id, "name": c.name} for c in classes]

        result.append(task_dict)

    return result


@router.get("/{task_id}", response_model=TaskWithAttachments)
def read_task(
        task_id: int,
        db: Session = Depends(get_db),
        current_admin: dict = Depends(get_current_admin)
):
    """
    获取任务详情
    """
    task = crud_task.get_with_attachments(db=db, task_id=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    return task


@router.put("/{task_id}", response_model=Task)
def update_task(
        task_id: int,
        title: str = Form(...),
        description: str = Form(None),
        max_duration: int = Form(None),
        max_attempts: int = Form(...),
        class_ids: str = Form(...),
        files: List[UploadFile] = File(None),
        db: Session = Depends(get_db),
        current_admin: dict = Depends(get_current_admin)
):
    """
    更新任务
    """
    task = crud_task.get(db=db, id=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
        # 解析表单数据
    task_data = {"task_id":task_id,"title": title, "description": description, "max_duration": max_duration, "max_attempts": max_attempts,
                 "class_ids": json.loads(class_ids), "task_type": task.task_type, "environment_id": task.environment_id}
    task_in = TaskUpdate(**task_data)

    # TODO：处理上传的附件（前后端都没弄）

    return crud_task.update(db=db, db_obj=task, obj_in=task_in)


@router.delete("/{task_id}", response_model=Task)
def delete_task(
        task_id: int,
        db: Session = Depends(get_db),
        current_admin: dict = Depends(get_current_admin)
):
    """
    删除任务
    """
    task = crud_task.get(db=db, id=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 删除任务附件文件
    upload_dir = os.path.join(settings.UPLOAD_FOLDER, f"task_{task_id}")
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)

    return crud_task.remove(db=db, id=task_id)


# 下面的代码是为了向后兼容，未来应迁移到student_tasks.py
@router.get("/student/list", response_model=List[Dict[str, Any]])
def list_student_tasks(
        db: Session = Depends(get_db),
        current_student: dict = Depends(get_current_student)
):
    """
    获取学生的任务列表，包括进行中的任务状态
    此端点保留以向后兼容，但建议使用新的/student/tasks端点
    """
    # 获取分配给学生所在班级的所有任务
    tasks = db.query(TaskDb).join(TaskAssDb).join(ClassDb).join(Student).filter(
        StudentDb.id == current_student["id"]
    ).all()

    if not tasks:
        return []

    result = []
    for task in tasks:
        # 查询学生最近的任务执行记录
        latest_student_task = db.query(StudentTaskDb).filter(
            StudentTaskDb.student_id == current_student["id"],
            StudentTaskDb.task_id == task.id
        ).order_by(StudentTaskDb.attempt_number.desc()).first()

        task_data = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "max_duration": task.max_duration,
            "max_attempts": task.max_attempts,
            "created_at": task.created_at,
            "task_type": task.task_type,  # 新增
            "status": "Not Started"
        }

        # 如果有任务执行记录
        if latest_student_task:
            # 重要修复：始终包含学生任务ID，无论状态如何
            task_data["student_task_id"] = latest_student_task.id

            # 设置状态
            task_data["status"] = latest_student_task.status  # 使用统一的状态字段

            if latest_student_task.end_at:
                task_data["end_at"] = latest_student_task.end_at

            if latest_student_task.task_type == "guacamole":
                # 对于ECS实例，查找IP
                ecs = db.query(ECSInstanceDb).filter(
                    ECSInstanceDb.student_task_id == latest_student_task.id
                ).first()
                if ecs and ecs.public_ip:
                    task_data["public_ip"] = ecs.public_ip

            task_data["start_at"] = latest_student_task.start_at
            task_data["attempt_number"] = latest_student_task.attempt_number

            # 添加剩余尝试次数信息
            task_data["remaining_attempts"] = task.max_attempts - \
                                              db.query(func.count(StudentTaskDb.id)).filter(
                                                  StudentTaskDb.student_id == current_student["id"],
                                                  StudentTaskDb.task_id == task.id
                                              ).scalar()
        else:
            task_data["remaining_attempts"] = task.max_attempts

        result.append(task_data)

    return result


@router.get("/student/{student_task_id}/status", response_model=Dict[str, Any])
def get_student_task_status(
        student_task_id: int,
        db: Session = Depends(get_db),
        current_student: Student = Depends(get_current_student)
):
    """
    获取学生任务的当前状态
    此端点保留以向后兼容，但建议使用新的/student/{student_task_id}端点
    """
    # 查询学生任务
    student_task = db.query(StudentTaskDb).filter(
        StudentTaskDb.id == student_task_id,
        StudentTaskDb.student_id == current_student["id"]
    ).first()
    task = db.query(TaskDb).filter(TaskDb.id == student_task.task_id).first()

    if not student_task or not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到任务"
        )

    # 构建响应
    response = {
        "id": student_task.id,
        "status": student_task.status,
        "start_at": student_task.start_at,
        "end_at": student_task.end_at,
        "task_type": student_task.task_type,
        "has_time_limit": False
    }
    if task and task.max_duration and student_task.start_at:
        elapsed = (datetime.datetime.utcnow() - student_task.start_at).total_seconds()
        remaining_seconds = max(0, task.max_duration * 60 - elapsed)
        remaining_time = int(remaining_seconds)
        response["remaining_time"] = remaining_time
        response["has_time_limit"] = True

    # 针对不同环境类型获取额外信息
    if student_task.task_type == "guacamole":
        # 获取ECS实例信息
        ecs = db.query(ECSInstanceDb).filter(
            ECSInstanceDb.student_task_id == student_task.id
        ).first()
        if ecs:
            response["ecs_instance_id"] = ecs.instance_id
            response["ecs_instance_status"] = ecs.status
            #response["ecs_ip_address"] = ecs.public_ip

    return response


@router.post("/student/start", response_model=Dict)
def start_task(
        task_in: StudentTaskCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_student: dict = Depends(get_current_student)
):
    """
    学生开始执行任务
    此端点保留以向后兼容，但建议使用新的/student/start-experiment/{task_id}端点
    """
    # 获取任务信息
    task = crud_task.get(db=db, id=task_in.task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 检查该学生是否有权限执行该任务
    student_tasks = crud_task.get_tasks_for_student(db=db, student_id=current_student["id"])
    if not any(t["id"] == task_in.task_id for t in student_tasks):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限执行该任务"
        )

    # 获取学生该任务的最新执行记录
    latest_task = crud_student_task.get_latest_for_student_task(
        db=db, student_id=current_student["id"], task_id=task_in.task_id
    )

    # 处理不同情况
    if not latest_task:
        # 首次执行任务
        student_task_obj = crud_student_task.create_student_task(
            db=db, student_id=current_student["id"], task_id=task_in.task_id, task_type=task.task_type
        )
    elif latest_task.status in ["stopped", "completed", "failed"]:
        # 之前的实例已结束，检查是否超过最大尝试次数
        if latest_task.attempt_number >= task.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"您已达到该任务的最大尝试次数 ({task.max_attempts})"
            )

        # 创建新的实验记录，尝试次数+1
        student_task_obj = crud_student_task.create_student_task(
            db=db,
            student_id=current_student["id"],
            task_id=task_in.task_id,
            task_type=task.task_type,
            attempt_number=latest_task.attempt_number + 1
        )
    else:
        # 当前有正在运行的实例
        # 针对guacamole类型，查询IP地址
        ip_address = None
        if latest_task.task_type == "guacamole":
            ecs = db.query(ECSInstance).filter(
                ECSInstance.student_task_id == latest_task.id
            ).first()
            if ecs:
                ip_address = ecs.public_ip

        return {
            "message": "该任务已经在运行中",
            "student_task_id": latest_task.id,
            "status": latest_task.status,
            "ecs_ip_address": ip_address
        }

    # 处理不同类型的环境启动
    if task.task_type == "guacamole":
        # 创建ECS实例
        background_tasks.add_task(create_ecs_instance, student_task_obj.id, task_in.task_id)

    return {
        "status": "preparing",
        "message": "正在准备实验环境，请稍候...",
        "student_task_id": student_task_obj.id
    }


@router.get("/student/{student_task_id}/status", response_model=Dict)
def check_task_status(
        student_task_id: int,
        db: Session = Depends(get_db),
        current_student: dict = Depends(get_current_student)
):
    """
    检查任务状态
    此端点保留以向后兼容，但建议使用新的/student/{student_task_id}端点
    """
    student_task = crud_student_task.get(db=db, id=student_task_id)
    if not student_task or student_task.student_id != current_student["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 获取任务信息
    task = crud_task.get(db=db, id=student_task.task_id)

    # 计算剩余时间
    remaining_minutes = None
    if task.max_duration and student_task.start_at:
        elapsed_seconds = (datetime.datetime.utcnow() - student_task.start_at).total_seconds()
        remaining_seconds = max(0, task.max_duration * 60 - elapsed_seconds)
        remaining_minutes = int(remaining_seconds / 60)

    # 构建响应
    response = {
        "status": student_task.status,
        "attempt_number": student_task.attempt_number,
        "max_attempts": task.max_attempts if task else None,
        "remaining_time": remaining_minutes,
        "has_time_limit": task.max_duration is not None if task else False
    }

    # 针对不同类型环境添加特定信息
    if student_task.task_type == "guacamole":
        ecs = db.query(ECSInstance).filter(
            ECSInstance.student_task_id == student_task.id
        ).first()
        if ecs:
            response["ecs_instance_status"] = ecs.status
            response["ecs_ip_address"] = ecs.public_ip

    return response
