from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from app.models.student import Student
from app.models.class_ import Class
from app.schemas.student import StudentCreate, StudentUpdate
from .base import CRUDBase


class CRUDStudent(CRUDBase[Student, StudentCreate, StudentUpdate]):
    def get_by_student_id(self, db: Session, *, student_id: str) -> Optional[Student]:
        return db.query(Student).filter(Student.student_id == student_id).first()
    
    def get_by_class(
        self, db: Session, *, class_id: int, skip: int = 0, limit: int = 100
    ) -> List[Student]:
        return db.query(Student).filter(Student.class_id == class_id).offset(skip).limit(limit).all()
    
    def authenticate(self, db: Session, *, student_id: str, name: str) -> Optional[Student]:
        return db.query(Student).filter(
            Student.student_id == student_id,
            Student.name == name
        ).first()
    
    def create_multi(self, db: Session, *, students_data: List[Dict[str, Any]], class_id: int) -> List[Student]:
        students = []
        for data in students_data:
            student = Student(
                student_id=data["student_id"],
                name=data["name"],
                class_id=class_id
            )
            db.add(student)
            students.append(student)
        
        db.commit()
        for student in students:
            db.refresh(student)
        
        return students


student = CRUDStudent(Student)