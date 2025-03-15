from celery import Celery
from celery.schedules import crontab
import logging
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ecs_tasks","app.tasks.jupyter_tasks"]
)

# 设置Celery配置
celery_app.conf.update(
    task_routes={
        # ECS任务
        "app.tasks.ecs_tasks.*": {"queue": "ecs"},
        # Jupyter任务
        "app.tasks.jupyter_tasks.*": {"queue": "jupyter"},
        # 默认任务
        "*": {"queue": "default"}
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_publish_retry=True,
    broker_connection_retry_on_startup=True,
    worker_concurrency=4,
)

celery_app.autodiscover_tasks([
    "app.tasks.ecs_tasks",
    "app.tasks.jupyter_tasks"
])

# 设置定时任务
celery_app.conf.beat_schedule = {
    "check-instance-status-every-10-seconds": {
        "task": "tasks.check_instance_status",
        "schedule": 10.0,  # 每10秒执行一次
    },
}

# 配置日志
logger = logging.getLogger(__name__)