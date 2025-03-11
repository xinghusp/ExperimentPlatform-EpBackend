from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import ALGORITHM
from app.crud.admin import admin as crud_admin
from app.crud.student import student as crud_student

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


class TokenData(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None


def get_current_user(
        db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 直接解码JWT
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        # 简化处理，直接从payload中获取信息
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        role = payload.get("role")
        if role is None:
            raise credentials_exception

        token_data = TokenData(sub=user_id, role=role)
    except JWTError:
        raise credentials_exception

    # 验证并获取用户
    if token_data.role == "admin":
        user = crud_admin.get(db, id=int(token_data.sub))
        if user is None:
            raise credentials_exception
        return {"id": user.id, "username": user.username, "role": "admin"}
    elif token_data.role == "student":
        user = crud_student.get(db, id=int(token_data.sub))
        if user is None:
            raise credentials_exception
        return {"id": user.id, "student_id": user.student_id, "name": user.name, "role": "student"}
    else:
        raise credentials_exception


def get_current_admin(
        current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


def get_current_student(
        current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid student credentials",
        )
    return current_user