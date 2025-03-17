import logging
import secrets
import time
import uuid
from datetime import datetime
from typing import Dict, Any
from celery import shared_task
from sqlalchemy import text

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.jupyter import jupyter_container
from app.crud.task import student_task, task
from app.services.docker_client import create_container, stop_container
import redis
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

# 创建Redis客户端
redis_client = redis.Redis.from_url(
    settings.CELERY_BROKER_URL,  # 暂时先与Celery共用Redis吧，以后再说
    encoding="utf-8",
    decode_responses=True
)


@shared_task
def create_jupyter_container_task(container_id: int, image: str, resource_config: Dict[str, Any]):
    """
    创建Jupyter容器的Celery任务
    """
    db = SessionLocal()
    try:
        # 获取容器记录
        container = jupyter_container.get(db, id=container_id)
        if not container:
            logger.error(f"Container not found: {container_id}")
            return {"status": "error", "message": "Container not found"}

        # 更新状态
        jupyter_container.update_status(db, id=container_id, status="Creating")
        student_task.update_status(db, student_task_id=container.student_task_id, status="Starting")
        student_task_model = student_task.get(db, id=container.student_task_id)
        task_model = task.get(db, id=student_task_model.task_id)

        # 创建容器
        logger.info(f"Creating Jupyter container with image {image}")

        # 设置内存和CPU限制
        memory = resource_config.get("memory", "1Gi")
        cpu = resource_config.get("cpu", "500m")
        memory_limit = resource_config.get("memory_limit", "2Gi")
        cpu_limit = resource_config.get("cpu_limit", "1")
        ports_map = resource_config.get("ports_map", {}).get("value",{})
        start_cmd = resource_config.get("command", None)

        print("ports_map:",ports_map,",start_cmd:",start_cmd)

        # 调用Docker API创建容器
        container_result = create_container(
            image=image,
            container_name=f"jupyter-{container_id}",
            memory=memory,
            cpu=cpu,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            ports=ports_map,
            start_cmd=start_cmd
        )


        # 更新容器信息
        jupyter_token = secrets.token_urlsafe(32)

        container.container_id=container_result["id"]
        container.container_name=container_result["name"]
        container.host=container_result["host"]
        container.port=container_result["port"]
        container.status="Running"
        container.nginx_token = jupyter_token
        db.add(container)
        db.commit()
        db.refresh(container)

        # 更新学生任务状态
        student_task.update_status(db, student_task_id=container.student_task_id, status="Running")

        # 存储认证串

        try:

            # 准备Redis存储数据
            jupyter_container_data = {
                "host": container_result["host"],
                "port": container_result["port"],
                "name": container_result["name"],
                "container_id": container_result["id"]
            }

            # 使用student_task_id作为键
            redis_key = f"jc:{jupyter_token}"
            redis_client.set(redis_key, json.dumps(jupyter_container_data), ex=task_model.max_duration if task_model.max_duration else None)

            logger.debug(f"Container information saved to Redis: {redis_key}")

        except Exception as e:
            logger.error(f"Failed to save container info to Redis: {str(e)}")

        logger.debug(f"Jupyter container created successfully: {container_id}")



        return {
            "status": "success",
            "container_id": container_result["id"],
            "port": container_result["port"]
        }

    except Exception as e:
        logger.error(f"Failed to create Jupyter container: {e}")

        # 更新状态为失败
        if container:
            jupyter_container.update_status(db, id=container_id, status="Error")
            student_task.update_status(db, student_task_id=container.student_task_id, status="Error")

        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        db.close()


@shared_task
def stop_jupyter_container_task(container_id: str):
    """
    停止Jupyter容器的Celery任务
    """
    db = SessionLocal()
    try:
        # 获取容器记录
        container = jupyter_container.get_by_container_id(db, container_id=container_id)
        if not container:
            logger.error(f"Container not found: {container_id}")
            return {"status": "error", "message": "Container not found"}

        # 停止容器
        logger.info(f"Stopping Jupyter container {container_id}")
        stop_result = stop_container(container_id)

        # 更新状态
        jupyter_container.update(
            db,
            db_obj=container,
            obj_in={
                "status": "Stopped",
                #"container_id": None
            }
        )

        # 更新学生任务状态
        student_task.update_status(db, student_task_id=container.student_task_id, status="Stopped")


        redis_key = f"jc:{container.nginx_token}"
        redis_client.delete(redis_key)


        return {"status": "success", "message": "Container stopped"}

    except Exception as e:
        logger.error(f"Failed to stop Jupyter container: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
