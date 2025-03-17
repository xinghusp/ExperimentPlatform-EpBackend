from celery import Celery
from celery.schedules import crontab
import logging
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ecs_tasks","app.tasks.jupyter_tasks", "app.tasks.cleanup_tasks"]
)

# 设置Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_publish_retry=True,
    broker_connection_retry_on_startup=True,
    worker_concurrency=4
)
#
celery_app.autodiscover_tasks([
    "app.tasks.ecs_tasks",
    "app.tasks.jupyter_tasks",
    "app.tasks.cleanup_tasks"

])

# 设置定时任务
celery_app.conf.beat_schedule = {
    "check-instance-status-every-10-seconds": {
        "task": "app.tasks.ecs_tasks.check_instance_status",
        "schedule": 10.0,  # 每10秒执行一次
    },
    "check-expire-task-every-60-seconds": {
        "task": "app.tasks.cleanup_tasks.cleanup_expired_tasks",
        "schedule": 60.0,  # 每60秒执行一次
    }
}


# 配置日志
logger = logging.getLogger(__name__)