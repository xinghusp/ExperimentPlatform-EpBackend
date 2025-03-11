from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# 密码上下文，用于密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT算法
ALGORITHM = "HS256"


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌

    Args:
        data: 要编码到令牌中的数据
        expires_delta: 令牌过期时间

    Returns:
        编码后的JWT令牌
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    # 添加标准JWT声明
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),  # 发布时间
        "nbf": datetime.utcnow(),  # Not Before
    })

    # 直接编码整个数据对象，不再嵌套JSON字符串
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希值"""
    return pwd_context.hash(password)