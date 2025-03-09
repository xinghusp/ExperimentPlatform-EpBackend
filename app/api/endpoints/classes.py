from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin
from app.schemas.class_ import ClassCreate, ClassUpdate, Class, ClassWithCount
from app.schemas.student import StudentCreate, StudentImport, Student
from app.crud.class_ import class_crud
from app.crud.student import student as crud_student

from app.models.student import Student as StudentDb

router = APIRouter()


@router.post("/", response_model=Class)
def create_class(
    class_in: ClassCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    创建班级
    """
    return class_crud.create_with_admin(db=db, obj_in=class_in, admin_id=current_admin["id"])


@router.get("/", response_model=List[ClassWithCount])
def read_classes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    获取班级列表
    """
    return class_crud.get_multi_with_student_count(db=db, skip=skip, limit=limit)


@router.get("/{class_id}", response_model=ClassWithCount)
def read_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    获取班级详情
    """
    class_obj = class_crud.get_with_student_count(db=db, class_id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )
    return class_obj


@router.put("/{class_id}", response_model=Class)
def update_class(
    class_id: int,
    class_in: ClassUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    更新班级信息
    """
    class_obj = class_crud.get(db=db, id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )
    return class_crud.update(db=db, db_obj=class_obj, obj_in=class_in)


@router.delete("/{class_id}", response_model=Class)
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    删除班级
    """
    class_obj = class_crud.get(db=db, id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )
    return class_crud.remove(db=db, id=class_id)


@router.post("/{class_id}/students", response_model=Student)
def create_student(
    class_id: int,
    student_in: StudentCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    添加学生
    """
    # 检查班级是否存在
    class_obj = class_crud.get(db=db, id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )
    
    # 检查学号是否已存在
    student = crud_student.get_by_student_id(db=db, student_id=student_in.student_id)
    if student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该学号已存在"
        )
    
    return crud_student.create(db=db, obj_in=student_in)


@router.post("/{class_id}/students/import", response_model=List[Student])
def import_students(
    class_id: int,
    import_data: StudentImport,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    批量导入学生
    """
    # 检查班级是否存在
    class_obj = class_crud.get(db=db, id=class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )
    
    # 检查导入数据是否为空
    if not import_data.students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="导入数据不能为空"
        )
    
    # 批量创建学生
    return crud_student.create_multi(
        db=db, students_data=import_data.students, class_id=class_id
    )


@router.get("/{class_id}/students", response_model=Dict[str, Any])
def read_students(
        class_id: int,
        db: Session = Depends(get_db),
        skip: int = Query(1, alias="page", ge=1),
        limit: int = Query(10, alias="limit", ge=1, le=100),
    current_admin: dict = Depends(get_current_admin)
):
    """
    获取指定班级的学生列表，带分页
    """
    # 检查班级是否存在
    # 从数据库中查询总数
    total = db.query(func.count(StudentDb.id)).filter(StudentDb.class_id == class_id).scalar()

    # 查询当前页的数据
    students = db.query(StudentDb).filter(
        StudentDb.class_id == class_id
    ).offset((skip-1) * limit).limit(limit).all()

    print(students)
    # 返回包含分页信息的响应
    return {
        "items": [Student.from_orm(student) for student in students],
        "total": total
    }


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
        student_id: int,
        db: Session = Depends(get_db),
        current_admin: dict = Depends(get_current_admin)
):
    """
    删除指定ID的学生
    """
    # 查询学生是否存在
    student = db.query(StudentDb).filter(StudentDb.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到指定的学生"
        )

    # 删除学生
    db.delete(student)
    db.commit()

    return None