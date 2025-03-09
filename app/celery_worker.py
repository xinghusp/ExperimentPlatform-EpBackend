from celery import Celery
from celery.schedules import crontab
import logging
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ecs_tasks"]
)

# 设置Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False
)

# 设置定时任务
celery_app.conf.beat_schedule = {
    "check-instance-status-every-10-seconds": {
        "task": "tasks.check_instance_status",
        "schedule": 10.0,  # 每10秒执行一次
    },
}

# 配置日志
logger = logging.getLogger(__name__)