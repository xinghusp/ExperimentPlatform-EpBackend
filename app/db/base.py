from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=200,       # 允许的最大连接数
    max_overflow=200,    # 允许的额外溢出连接数
    pool_timeout=30,    # 连接池超时时间
    pool_recycle=1800   # 连接回收时间，避免长时间未使用的连接失效
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()