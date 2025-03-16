from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.ecs import ECSInstance
from app.schemas.ecs import ECSInstanceCreate, ECSInstanceUpdate
from .base import CRUDBase


class CRUDECSInstance(CRUDBase[ECSInstance, ECSInstanceCreate, ECSInstanceUpdate]):
    def get_by_student_task_id(
            self, db: Session, *, student_task_id: int
    ) -> Optional[ECSInstance]:
        return db.query(ECSInstance).filter(
            ECSInstance.student_task_id == student_task_id
        ).first()

    def get_by_instance_id(
            self, db: Session, *, instance_id: str
    ) -> Optional[ECSInstance]:
        return db.query(ECSInstance).filter(
            ECSInstance.instance_id == instance_id
        ).first()

    def update_status_by_instance_name(self, db: Session, *, instance_name: str, status: str, instance_id: str=None, password:str=None) -> ECSInstance:
        instance = db.query(ECSInstance).filter(
            ECSInstance.instance_name == instance_name
        ).first()
        if not instance:
            return None

        instance.status = status
        if instance_id:
            instance.instance_id = instance_id
        if password:
            instance.password = password
        instance.updated_at = datetime.utcnow()

        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def update_status(
            self, db: Session, *, instance_id: str, status: str,
            public_ip: str = None, private_ip: str = None
    ) -> ECSInstance:
        """更新ECS实例状态"""
        instance = self.get_by_instance_id(db, instance_id=instance_id)
        if not instance:
            return None

        instance.status = status
        if public_ip:
            instance.public_ip = public_ip
        if private_ip:
            instance.private_ip = private_ip
        instance.updated_at = datetime.utcnow()

        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def get_active_instances(
            self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ECSInstance]:
        """获取活跃(非停止状态)的实例"""
        return db.query(ECSInstance).filter(
            ECSInstance.status.notin_(["Stopped", "Error"])
        ).offset(skip).limit(limit).all()


ecs_instance = CRUDECSInstance(ECSInstance)