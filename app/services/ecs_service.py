import os
import json
import time
import uuid
import asyncio
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.tasks.ecs_tasks import create_ecs_instance_task, stop_ecs_instance_task

logger = logging.getLogger(__name__)


async def create_instance(
        task_id: int,
        student_task_id: int
) -> Dict[str, Any]:
    """
    创建ECS实例
    """
    # 生成实例名称
    instance_name = f"task-{task_id}-{str(uuid.uuid4())[:8]}"

    # 从资源配置中提取参数
    # instance_type = resource_config.get("instance_type",None)
    # internet_max_bandwidth = resource_config.get("bandwidth",None)
    # region_id = resource_config.get("region_id",None)
    # security_group_id = resource_config.get("security_group_id",None)
    # vswitch_id = resource_config.get("vswitch_id",None)
    # spot_strategy = resource_config.get("spot_strategy", None)
    #
    # # 如果配置中未提供密码，则随机生成
    # password = resource_config.get("password", f"Abc{uuid.uuid4().hex[:10]}!")

    # 异步创建实例
    create_ecs_instance_task.delay(
        student_task_id=student_task_id,
        instance_name=instance_name,
    )

    # 返回初始信息
    return {
        "instance_id": None,  # 实例ID将由异步任务填充
        "instance_name": instance_name
    }


async def stop_instance(instance_id: str) -> bool:
    """
    停止并释放ECS实例
    """
    try:
        # 异步停止实例
        stop_ecs_instance_task.delay(instance_id=instance_id)
        return True
    except Exception as e:
        logger.error(f"Failed to stop instance {instance_id}: {e}")
        return False