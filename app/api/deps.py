import json
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import ALGORITHM
from app.models.admin import Administrator
from app.models.student import Student
from app.crud.admin import admin as crud_admin
from app.crud.student import student as crud_student

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


class TokenData(BaseModel):
    id: Optional[int] = None
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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        payload_data = payload.get("sub")
        if payload_data is None:
            raise credentials_exception

        # Parse the nested JSON string
        #print("payload_data: ", payload_data)
        print("payload_data: ", payload_data)
        print("payload_data type: ", type(payload_data))
        nested_payload = json.loads(payload_data.replace("'", '"'))
        user_id: str = nested_payload.get("sub")
        if user_id is None:
            raise credentials_exception
        role: str = nested_payload.get("role", "")
        token_data = TokenData(id=int(user_id), role=role)
    except JWTError:
        raise credentials_exception
    
    if token_data.role == "admin":
        user = crud_admin.get(db, id=token_data.id)
        if user is None:
            raise credentials_exception
        return {"id": user.id, "username": user.username, "role": "admin"}
    elif token_data.role == "student":
        user = crud_student.get(db, id=token_data.id)
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