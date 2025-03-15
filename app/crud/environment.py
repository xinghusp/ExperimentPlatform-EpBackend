from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.environment import EnvironmentTemplate
from app.schemas.environment import EnvironmentTemplateCreate, EnvironmentTemplateUpdate
from .base import CRUDBase


class CRUDEnvironmentTemplate(CRUDBase[EnvironmentTemplate, EnvironmentTemplateCreate, EnvironmentTemplateUpdate]):
    def create_with_admin(
            self, db: Session, *, obj_in: EnvironmentTemplateCreate, admin_id: int
    ) -> EnvironmentTemplate:
        obj_in_data = obj_in.dict()
        db_obj = EnvironmentTemplate(**obj_in_data, created_by=admin_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_type(
            self, db: Session, *, type: str, skip: int = 0, limit: int = 100
    ) -> List[EnvironmentTemplate]:
        return db.query(EnvironmentTemplate).filter(
            EnvironmentTemplate.type == type
        ).offset(skip).limit(limit).all()

    def get_for_task_type(
            self, db: Session, *, task_type: str, skip: int = 0, limit: int = 100
    ) -> List[EnvironmentTemplate]:
        """获取适用于特定任务类型的环境模板"""
        return db.query(EnvironmentTemplate).filter(
            EnvironmentTemplate.type == task_type
        ).offset(skip).limit(limit).all()


environment_template = CRUDEnvironmentTemplate(EnvironmentTemplate)