from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List
import secrets


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    MYSQL_SERVER: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str = "ExperimentalPlatformDb"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # 阿里云相关配置
    ALIYUN_ACCESS_KEY_ID: str
    ALIYUN_ACCESS_KEY_SECRET: str
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:8080", "http://localhost:3000"]
    
    # 文件存储
    UPLOAD_FOLDER: str = "static/uploads"
    
    # Guacamole配置
    GUACAMOLE_HOST: str = "localhost"
    GUACAMOLE_PORT: int = 4822

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
    }

    DOCKER_HOST: str = "tcp://localhost:2375"
    DOCKER_HOST_IP: str = "localhost"  # 使用远程服务器的IP或域名
    DOCKER_TLS_VERIFY: bool = False
    DOCKER_CERT_PATH: Optional[str] = None

    print(GUACAMOLE_HOST)

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.SQLALCHEMY_DATABASE_URI is None:
            self.SQLALCHEMY_DATABASE_URI = (
                f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
                f"@{self.MYSQL_SERVER}/{self.MYSQL_DB}"
            )


settings = Settings()