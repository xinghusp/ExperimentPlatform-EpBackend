from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.class_ import Class
from app.models.student import Student
from app.schemas.class_ import ClassCreate, ClassUpdate
from .base import CRUDBase


class CRUDClass(CRUDBase[Class, ClassCreate, ClassUpdate]):
    def create_with_admin(
        self, db: Session, *, obj_in: ClassCreate, admin_id: int
    ) -> Class:
        obj_in_data = obj_in.dict()
        db_obj = Class(**obj_in_data, created_by=admin_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_admin(
        self, db: Session, *, admin_id: int, skip: int = 0, limit: int = 100
    ) -> List[Class]:
        return db.query(Class).filter(Class.created_by == admin_id).offset(skip).limit(limit).all()
    
    def get_with_student_count(self, db: Session, *, class_id: int) -> Dict[str, Any]:
        class_obj = db.query(Class).filter(Class.id == class_id).first()
        if not class_obj:
            return None
        
        student_count = db.query(func.count(Student.id)).filter(
            Student.class_id == class_id
        ).scalar()
        
        result = {
            "id": class_obj.id,
            "name": class_obj.name,
            "description": class_obj.description,
            "created_at": class_obj.created_at,
            "updated_at": class_obj.updated_at,
            "created_by": class_obj.created_by,
            "student_count": student_count
        }
        return result
    
    def get_multi_with_student_count(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        classes = db.query(Class).offset(skip).limit(limit).all()
        result = []
        
        for class_obj in classes:
            student_count = db.query(func.count(Student.id)).filter(
                Student.class_id == class_obj.id
            ).scalar()
            
            class_data = {
                "id": class_obj.id,
                "name": class_obj.name,
                "description": class_obj.description,
                "created_at": class_obj.created_at,
                "updated_at": class_obj.updated_at,
                "created_by": class_obj.created_by,
                "student_count": student_count
            }
            result.append(class_data)
        
        return result


class_crud = CRUDClass(Class)