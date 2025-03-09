from typing import Dict, List, Any, Optional

import pytz
from celery import shared_task
import json
import datetime
import logging
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.ali_cloud import ali_cloud_service
from app.crud.task import student_task as crud_student_task
from app.crud.task import celery_task_log as crud_celery_log
from app.models.task import Task, StudentTask

logger = logging.getLogger(__name__)


@shared_task(name="tasks.create_ecs_instance")
def create_ecs_instance(student_task_id: int, task_id: int) -> Dict[str, Any]:
    """创建ECS实例任务"""
    db = SessionLocal()
    try:
        # 记录Celery任务开始
        crud_celery_log.create_log(
            db=db,
            celery_task_id=task_id,
            task_name="create_ecs_instance",
            status="STARTED",
            args=json.dumps({"student_task_id": student_task_id}),
            student_task_id=student_task_id,

        )

        # 获取学生任务信息
        student_task_obj = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task_obj:
            error_msg = f"Student task with id {student_task_id} not found"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=create_ecs_instance.request.id,
                status="FAILURE",
                result=error_msg
            )
            return {"success": False, "error": error_msg}

        # 获取任务配置信息
        task_obj = db.query(Task).filter(Task.id == student_task_obj.task_id).first()
        if not task_obj:
            error_msg = f"Task with id {student_task_obj.task_id} not found"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=create_ecs_instance.request.id,
                status="FAILURE",
                result=error_msg
            )
            return {"success": False, "error": error_msg}

        # 计算自动释放时间
        now = datetime.datetime.utcnow()
        if task_obj.max_duration:
            # 预留10分钟冗余量
            auto_release_time = now + datetime.timedelta(minutes=task_obj.max_duration + 10)
        else:
            # 默认24小时后释放
            auto_release_time = now + datetime.timedelta(hours=24)

        # 更新数据库中的自动释放时间
        student_task_obj.auto_release_time = auto_release_time.astimezone(pytz.timezone('Asia/Shanghai'))
        db.add(student_task_obj)
        db.commit()

        # 调用阿里云SDK创建ECS实例
        result = ali_cloud_service.create_ecs_instance(
            region_id=task_obj.region_id,
            image_id=task_obj.image_id,
            instance_type=task_obj.instance_type,
            security_group_id=task_obj.security_group_id,
            vswitch_id=task_obj.vswitch_id,
            internet_max_bandwidth_out=task_obj.internet_max_bandwidth_out,
            spot_strategy=task_obj.spot_strategy,
            password=task_obj.password,
            auto_release_time=auto_release_time,
            custom_params=task_obj.custom_params
        )

        if not result["success"]:
            crud_celery_log.update_status(
                db=db,
                celery_task_id=create_ecs_instance.request.id,
                status="FAILURE",
                result=json.dumps({"error": result["error"]})
            )

            # 更新学生任务状态
            student_task_obj.ecs_instance_status = "Error"
            db.add(student_task_obj)
            db.commit()

            return {"success": False, "error": result["error"]}

        # 如果成功，更新学生任务记录
        instance_id = result["instance_ids"][0] if result["instance_ids"] else None
        if instance_id:
            student_task_obj.ecs_instance_id = instance_id
            student_task_obj.ecs_instance_status = "Starting"
            db.add(student_task_obj)
            db.commit()

        crud_celery_log.update_status(
            db=db,
            celery_task_id=create_ecs_instance.request.id,
            status="SUCCESS",
            result=json.dumps(result)
        )

        return {"success": True, "result": result}

    except Exception as e:
        logger.exception("Error creating ECS instance")
        crud_celery_log.update_status(
            db=db,
            celery_task_id=create_ecs_instance.request.id,
            status="FAILURE",
            result=str(e)
        )
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(name="tasks.check_instance_status")
def check_instance_status() -> Dict[str, Any]:
    """检查实例状态任务"""
    db = SessionLocal()
    try:
        # 获取所有活跃的实例
        active_instances = crud_student_task.get_active_instances(db=db)
        if not active_instances:
            return {"success": True, "message": "No active instances found"}

        # 按region分组处理，每次最多处理100个实例
        region_instances = {}
        for instance in active_instances:
            if not instance.ecs_instance_id:
                continue

            task = db.query(Task).filter(Task.id == instance.task_id).first()
            if not task:
                continue

            region_id = task.region_id
            if region_id not in region_instances:
                region_instances[region_id] = []

            region_instances[region_id].append({
                "instance_id": instance.ecs_instance_id,
                "student_task_id": instance.id
            })

        # 处理每个区域的实例
        for region_id, instances in region_instances.items():
            # 每组最多处理100个实例
            for i in range(0, len(instances), 100):
                batch = instances[i:i + 100]
                instance_ids = [inst["instance_id"] for inst in batch]
                logger.info(f"Checking {len(instance_ids)} instances in region {region_id}")
                # 调用阿里云SDK检查实例状态
                result = ali_cloud_service.describe_instance(
                    instance_ids=instance_ids
                )

                if not result["success"]:
                    logger.error(f"Error checking instances in region {region_id}: {result['error']}")
                    continue

                # 处理返回的信息
                instance_info = {
                    inst["InstanceId"]: inst
                    for inst in result["instances"]
                }
                logger.info(f"Instance info in region {region_id}: {instance_info}")

                # 更新数据库中的状态
                for instance in batch:
                    instance_id = instance["instance_id"]
                    student_task_id = instance["student_task_id"]

                    if instance_id in instance_info.keys():
                        info = instance_info[instance_id]
                        crud_student_task.update_instance_status(
                            db=db,
                            student_task_id=student_task_id,
                            status=info["Status"],
                            ip_address=info["VpcAttributes"]["PrivateIpAddress"]["IpAddress"][0] if len(info["VpcAttributes"]["PrivateIpAddress"]["IpAddress"])>0 else None
                        )
                    else:
                        # 如果返回中没有该实例，则标记为Error
                        crud_student_task.update_instance_status(
                            db=db,
                            student_task_id=student_task_id,
                            status="Error"
                        )

        return {"success": True}

    except Exception as e:
        logger.exception("Error checking instance status")
        return {"success": False, "error": str(e)}
    finally:
        db.close()



@shared_task(name="tasks.delete_instance")
def delete_instance(student_task_id: int,task_id: int) -> Dict[str, Any]:
    """删除ECS实例任务"""
    db = SessionLocal()
    try:
        # 记录Celery任务开始
        crud_celery_log.create_log(
            db=db,
            celery_task_id=task_id,
            task_name="delete_instance",
            status="STARTED",
            args=json.dumps({"student_task_id": student_task_id}),
            student_task_id=student_task_id
        )

        # 获取学生任务信息
        student_task_obj = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task_obj:
            error_msg = f"Student task with id {student_task_id} not found"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=task_id,
                status="FAILURE",
                result=error_msg
            )
            return {"success": False, "error": error_msg}

        if not student_task_obj.ecs_instance_id:
            crud_celery_log.update_status(
                db=db,
                celery_task_id=task_id,
                status="SUCCESS",
                result="No ECS instance ID found, marking task as completed"
            )

            # 更新任务状态
            student_task_obj.ecs_instance_status = "Stopped"
            student_task_obj.end_at = datetime.datetime.now()
            db.add(student_task_obj)
            db.commit()

            return {"success": True, "message": "No ECS instance to delete"}

        # 获取任务配置信息
        task_obj = db.query(Task).filter(Task.id == student_task_obj.task_id).first()
        if not task_obj:
            error_msg = f"Task with id {student_task_obj.task_id} not found"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=delete_instance.request.id,
                status="FAILURE",
                result=error_msg
            )
            return {"success": False, "error": error_msg}

        # 调用阿里云SDK删除ECS实例
        result = ali_cloud_service.delete_instance(
            region_id=task_obj.region_id,
            instance_id=student_task_obj.ecs_instance_id,
            force=True
        )

        # 无论删除成功与否，都更新任务状态
        student_task_obj.ecs_instance_status = "Stopped"
        student_task_obj.end_at = datetime.datetime.now()
        db.add(student_task_obj)
        db.commit()

        if not result["success"]:
            crud_celery_log.update_status(
                db=db,
                celery_task_id=delete_instance.request.id,
                status="FAILURE",
                result=json.dumps({"error": result["error"]})
            )
            return {"success": False, "error": result["error"]}

        crud_celery_log.update_status(
            db=db,
            celery_task_id=delete_instance.request.id,
            status="SUCCESS",
            result=json.dumps(result)
        )

        return {"success": True, "result": result}

    except Exception as e:
        logger.exception("Error deleting ECS instance")
        crud_celery_log.update_status(
            db=db,
            celery_task_id=delete_instance.request.id,
            status="FAILURE",
            result=str(e)
        )
        return {"success": False, "error": str(e)}
    finally:
        db.close()