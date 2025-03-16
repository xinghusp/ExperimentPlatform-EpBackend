import logging
import time
from typing import Dict, Any
from celery import shared_task

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.jupyter import jupyter_container
from app.crud.task import student_task
from app.services.docker_client import create_container, stop_container

logger = logging.getLogger(__name__)


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

        # 创建容器
        logger.info(f"Creating Jupyter container with image {image}")

        # 设置内存和CPU限制
        memory = resource_config.get("memory", "1Gi")
        cpu = resource_config.get("cpu", "500m")
        memory_limit = resource_config.get("memory_limit", "2Gi")
        cpu_limit = resource_config.get("cpu_limit", "1")

        # 调用Docker API创建容器
        container_result = create_container(
            image=image,
            container_name=f"jupyter-{container_id}",
            memory=memory,
            cpu=cpu,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit
        )

        # 更新容器信息
        jupyter_container.update(
            db,
            db_obj=container,
            obj_in={
                "container_id": container_result["id"],
                "container_name": container_result["name"],
                "host": container_result["host"],
                "port": container_result["port"],
                "status": "Running"
            }
        )

        # 更新学生任务状态
        student_task.update_status(db, student_task_id=container.student_task_id, status="Running")

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
                "status": "stopped",
                "container_id": None
            }
        )

        # 更新学生任务状态
        student_task.update_status(db, student_task_id=container.student_task_id, status="completed")

        return {"status": "success", "message": "Container stopped"}

    except Exception as e:
        logger.error(f"Failed to stop Jupyter container: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()