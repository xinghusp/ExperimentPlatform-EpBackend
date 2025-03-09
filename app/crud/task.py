from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
import datetime
from app.models.task import Task, TaskAttachment, TaskAssignment, StudentTask, CeleryTaskLog
from app.models.class_ import Class
from app.models.student import Student
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskAttachmentCreate,
    StudentTaskCreate, CeleryTaskLogCreate
)
from app.models.task import StudentTask as StudentTaskDb
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
        
        result = {
            **task.__dict__,
            "attachments": [attachment.__dict__ for attachment in attachments]
        }
        return result
    
    def create_attachment(
        self, db: Session, *, obj_in: TaskAttachmentCreate, task_id: int
    ) -> TaskAttachment:
        db_obj = TaskAttachment(**obj_in.dict(), task_id=task_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update_assignment(
        self, db: Session, *, task_id: int, class_ids: List[int]
    ) -> None:
        # 删除现有分配
        db.query(TaskAssignment).filter(TaskAssignment.task_id == task_id).delete()
        
        # 创建新分配
        for class_id in class_ids:
            task_assignment = TaskAssignment(
                task_id=task_id,
                class_id=class_id
            )
            db.add(task_assignment)
        
        db.commit()
    
    def get_tasks_for_student(
        self, db: Session, *, student_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict]:
        # 获取学生所属班级
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return []
        
        # 获取分配给该班级的任务
        tasks = (
            db.query(Task)
            .join(TaskAssignment, TaskAssignment.task_id == Task.id)
            .filter(TaskAssignment.class_id == student.class_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        result = []
        for task in tasks:
            # 查找该学生的任务执行情况
            student_task = (
                db.query(StudentTask)
                .filter(
                    StudentTask.student_id == student_id,
                    StudentTask.task_id == task.id
                )
                .order_by(StudentTask.id.desc())
                .first()
            )
            
            task_data = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "max_duration": task.max_duration,
                "max_attempts": task.max_attempts,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "status": None,
                "attempt_number": 0,
                "remaining_attempts": task.max_attempts
            }
            
            if student_task:
                task_data["status"] = student_task.ecs_instance_status
                task_data["attempt_number"] = student_task.attempt_number
                task_data["remaining_attempts"] = task.max_attempts - student_task.attempt_number
            
            result.append(task_data)
        
        return result


class CRUDStudentTask(CRUDBase[StudentTask, StudentTaskCreate, StudentTaskCreate]):
    def create_student_task(
        self, db: Session, *, student_id: int, task_id: int, attempt_number: int = 1
    ) -> StudentTask:
        db_obj = StudentTask(
            student_id=student_id,
            task_id=task_id,
            attempt_number=attempt_number,
            ecs_instance_status="Preparing",
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
    
    def get_active_instances(
        self, db: Session, *, limit: int = 100
    ) -> List[StudentTaskDb]:
        return (
            db.query(StudentTaskDb)
            .filter(
                StudentTaskDb.ecs_instance_status.notin_(["Stopped", "Error"])
            )
            .limit(limit)
            .all()
        )
    
    def update_instance_status(
        self, db: Session, *, student_task_id: int, status: str, ip_address: str = None
    ) -> StudentTask:
        student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task:
            return None
        
        student_task.ecs_instance_status = status
        if ip_address:
            student_task.ecs_ip_address = ip_address
        
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
        student_task.ecs_instance_status = "Stopped"
        db.add(student_task)
        db.commit()
        db.refresh(student_task)
        return student_task


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