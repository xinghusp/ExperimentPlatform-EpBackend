from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
import datetime
from app.models.task import Task, TaskAttachment, TaskAssignment, StudentTask, CeleryTaskLog
from app.models.class_ import Class
from app.models.student import Student
from app.models.environment import EnvironmentTemplate
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskAttachmentCreate,
    StudentTaskCreate, CeleryTaskLogCreate
)
from app.models.task import StudentTask as StudentTaskDb
from app.models.ecs import ECSInstance  # 添加导入
from app.models.jupyter import JupyterContainer  # 添加导入
from .base import CRUDBase


class CRUDTask(CRUDBase[Task, TaskCreate, TaskUpdate]):
    def create_with_admin(
            self, db: Session, *, obj_in: TaskCreate, admin_id: int
    ) -> Task:
        obj_in_data = obj_in.dict(exclude={"class_ids"})
        db_obj = Task(**obj_in_data, created_by=admin_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        # 创建任务分配
        for class_id in obj_in.class_ids:
            task_assignment = TaskAssignment(
                task_id=db_obj.id,
                class_id=class_id
            )
            db.add(task_assignment)

        db.commit()
        return db_obj

    def get_with_attachments(self, db: Session, *, task_id: int) -> Optional[Dict]:
        task = db.query(Task).options(joinedload(Task.classes)).filter(Task.id == task_id).first()
        if not task:
            return None

        attachments = db.query(TaskAttachment).filter(
            TaskAttachment.task_id == task_id
        ).all()

        # 获取环境模板信息（如果有）
        environment = None
        if task.environment_id:
            environment = db.query(EnvironmentTemplate).filter(
                EnvironmentTemplate.id == task.environment_id
            ).first()

        # Convert task to dict (excluding SQLAlchemy attributes)
        task_dict = {k: v for k, v in task.__dict__.items() if not k.startswith('_')}

        # Convert classes to a list of dicts
        classes_data = []
        if hasattr(task, 'classes'):
            classes_data = [{"id": cls.id, "name": cls.name, "description": cls.description}
                            for cls in task.classes]

        # Add classes to the result
        task_dict["classes"] = classes_data

        result = {
            **task_dict,
            "attachments": [{k: v for k, v in attachment.__dict__.items() if not k.startswith('_')}
                            for attachment in attachments],
            "environment": {k: v for k, v in environment.__dict__.items() if not k.startswith('_')}
            if environment else None
        }
        return result

    # 其他方法保持不变...

    def set_task_environment(
            self, db: Session, *, task_id: int, environment_id: int, task_type: str
    ) -> Task:
        """为任务设置环境模板和类型"""
        task = self.get(db, id=task_id)
        if not task:
            return None

        # 更新任务类型和环境ID
        task.task_type = task_type
        task.environment_id = environment_id

        db.add(task)
        db.commit()
        db.refresh(task)
        return task


class CRUDStudentTask(CRUDBase[StudentTask, StudentTaskCreate, StudentTaskCreate]):
    def create_student_task(
            self, db: Session, *, student_id: int, task_id: int, task_type: str, attempt_number: int = 1
    ) -> StudentTask:
        # 获取任务信息以获取task_type
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None

        db_obj = StudentTask(
            student_id=student_id,
            task_id=task_id,
            attempt_number=attempt_number,
            task_type=task.task_type,  # 使用任务的类型
            status="pending",
            start_at=datetime.datetime.now()
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_latest_for_student_task(
            self, db: Session, *, student_id: int, task_id: int
    ) -> Optional[StudentTask]:
        return (
            db.query(StudentTask)
            .filter(
                StudentTask.student_id == student_id,
                StudentTask.task_id == task_id
            )
            .order_by(StudentTask.id.desc())
            .first()
        )

    def get_active_tasks(
            self, db: Session, *, limit: int = 100
    ) -> List[StudentTaskDb]:
        return (
            db.query(StudentTaskDb)
            .filter(
                StudentTaskDb.status.notin_(["completed", "failed", "stopped"])
            )
            .limit(limit)
            .all()
        )

    def update_status(
            self, db: Session, *, student_task_id: int, status: str
    ) -> StudentTask:
        """更新学生任务状态"""
        student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task:
            return None

        student_task.status = status

        db.add(student_task)
        db.commit()
        db.refresh(student_task)
        return student_task

    def update_heartbeat(
            self, db: Session, *, student_task_id: int
    ) -> StudentTask:
        student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task:
            return None

        student_task.last_heartbeat = datetime.datetime.now()
        db.add(student_task)
        db.commit()
        db.refresh(student_task)
        return student_task

    def end_experiment(
            self, db: Session, *, student_task_id: int
    ) -> StudentTask:
        student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task:
            return None

        student_task.end_at = datetime.datetime.now()
        student_task.status = "Stopped"
        db.add(student_task)
        db.commit()
        db.refresh(student_task)
        return student_task

    def get_task_with_environment_detail(
            self, db: Session, *, student_task_id: int
    ) -> Optional[Dict]:
        """获取学生任务详情，包括环境实例信息"""
        student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task:
            return None

        task = db.query(Task).filter(Task.id == student_task.task_id).first()
        if not task:
            return None

        # 获取环境模板
        environment = None
        if task.environment_id:
            environment = db.query(EnvironmentTemplate).filter(
                EnvironmentTemplate.id == task.environment_id
            ).first()

        # 根据任务类型获取相应的环境实例
        instance_info = None
        if student_task.task_type == "guacamole":
            # 获取ECS实例
            ecs_instance = db.query(ECSInstance).filter(
                ECSInstance.student_task_id == student_task.id
            ).first()
            if ecs_instance:
                instance_info = {
                    "type": "ecs",
                    "instance_id": ecs_instance.instance_id,
                    "status": ecs_instance.status,
                    "public_ip": ecs_instance.public_ip,
                    "instance_type": ecs_instance.instance_type
                }
        elif student_task.task_type == "jupyter":
            # 获取Jupyter容器
            jupyter = db.query(JupyterContainer).filter(
                JupyterContainer.student_task_id == student_task.id
            ).first()
            if jupyter:
                instance_info = {
                    "type": "jupyter",
                    "container_id": jupyter.container_id,
                    "status": jupyter.status,
                    "host": jupyter.host,
                    "port": jupyter.port
                }

        return {
            "student_task": student_task.__dict__,
            "task": task.__dict__,
            "environment": environment.__dict__ if environment else None,
            "instance": instance_info
        }


class CRUDCeleryTaskLog(CRUDBase[CeleryTaskLog, CeleryTaskLogCreate, CeleryTaskLogCreate]):
    def create_log(
            self, db: Session, *, celery_task_id: str, task_name: str, status: str,
            args: str = None, result: str = None, student_task_id: int = None
    ) -> CeleryTaskLog:
        db_obj = CeleryTaskLog(
            task_id=celery_task_id,
            task_name=task_name,
            status=status,
            args=args,
            result=result,
            student_task_id=student_task_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
            self, db: Session, *, celery_task_id: str, status: str, result: str = None
    ) -> CeleryTaskLog:
        log = db.query(CeleryTaskLog).filter(CeleryTaskLog.task_id == celery_task_id).first()
        if not log:
            return None

        log.status = status
        if result:
            log.result = result

        db.add(log)
        db.commit()
        db.refresh(log)
        return log


task = CRUDTask(Task)
student_task = CRUDStudentTask(StudentTask)
celery_task_log = CRUDCeleryTaskLog(CeleryTaskLog)