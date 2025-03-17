from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.jupyter import JupyterContainer
from app.schemas.jupyter import JupyterContainerCreate, JupyterContainerUpdate
from .base import CRUDBase


class CRUDJupyterContainer(CRUDBase[JupyterContainer, JupyterContainerCreate, JupyterContainerUpdate]):
    def get_by_student_task_id(
            self, db: Session, *, student_task_id: int
    ) -> Optional[JupyterContainer]:
        return db.query(JupyterContainer).filter(
            JupyterContainer.student_task_id == student_task_id
        ).first()

    def get_by_container_id(
            self, db: Session, *, container_id: str
    ) -> Optional[JupyterContainer]:
        return db.query(JupyterContainer).filter(
            JupyterContainer.container_id == container_id
        ).first()

    def update_status(
            self, db: Session, *, id: int, status: str
    ) -> JupyterContainer:
        """更新Jupyter容器状态"""
        container = self.get(db, id=id)
        if not container:
            return None

        container.status = status
        db.add(container)
        db.commit()
        db.refresh(container)
        return container

    def update_last_active(
            self, db: Session, *, id: int
    ) -> JupyterContainer:
        """更新最后活动时间"""
        container = self.get(db, id=id)
        if not container:
            return None

        container.last_active = datetime.utcnow()
        db.add(container)
        db.commit()
        db.refresh(container)
        return container

    def get_active_containers(
            self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[JupyterContainer]:
        """获取活跃的容器"""
        return db.query(JupyterContainer).filter(
            JupyterContainer.status == "running"
        ).offset(skip).limit(limit).all()


jupyter_container = CRUDJupyterContainer(JupyterContainer)