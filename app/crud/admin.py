from typing import Optional
from sqlalchemy.orm import Session
from app.models.admin import Administrator
from app.schemas.admin import AdminCreate, AdminUpdate
from app.core.security import get_password_hash, verify_password
from .base import CRUDBase


class CRUDAdmin(CRUDBase[Administrator, AdminCreate, AdminUpdate]):
    def create(self, db: Session, *, obj_in: AdminCreate) -> Administrator:
        db_obj = Administrator(
            username=obj_in.username,
            password=get_password_hash(obj_in.password),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def authenticate(self, db: Session, *, username: str, password: str) -> Optional[Administrator]:
        admin = db.query(Administrator).filter(Administrator.username == username).first()
        if not admin:
            return None
        if not verify_password(password, admin.password):
            return None
        return admin
    
    def update_password(self, db: Session, *, db_obj: Administrator, new_password: str) -> Administrator:
        db_obj.password = get_password_hash(new_password)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


admin = CRUDAdmin(Administrator)