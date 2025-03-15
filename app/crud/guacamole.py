from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.guacamole import GuacamoleConnection
from app.schemas.guacamole import GuacamoleConnectionCreate, GuacamoleConnectionUpdate
from .base import CRUDBase


class CRUDGuacamoleConnection(CRUDBase[GuacamoleConnection, GuacamoleConnectionCreate, GuacamoleConnectionUpdate]):
    def get_by_ecs_instance_id(
            self, db: Session, *, ecs_instance_id: int
    ) -> Optional[GuacamoleConnection]:
        return db.query(GuacamoleConnection).filter(
            GuacamoleConnection.ecs_instance_id == ecs_instance_id
        ).first()

    def get_by_connection_id(
            self, db: Session, *, connection_id: str
    ) -> Optional[GuacamoleConnection]:
        return db.query(GuacamoleConnection).filter(
            GuacamoleConnection.connection_id == connection_id
        ).first()

    def update_last_accessed(
            self, db: Session, *, id: int
    ) -> GuacamoleConnection:
        """更新最后访问时间"""
        connection = self.get(db, id=id)
        if not connection:
            return None

        connection.last_accessed = datetime.now()
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return connection


guacamole_connection = CRUDGuacamoleConnection(GuacamoleConnection)