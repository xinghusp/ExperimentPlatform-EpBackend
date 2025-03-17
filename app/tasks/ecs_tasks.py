import random
import uuid
from typing import Dict, List, Any, Optional

import pytz
import json
import datetime
import logging
from sqlalchemy.orm import Session

from app.celery_worker import celery_app
from app.db.session import SessionLocal
from app.models.ecs import ECSInstance
from app.models.environment import EnvironmentTemplate
from app.services.ali_cloud import ali_cloud_service
from app.crud.task import student_task as crud_student_task, student_task
from app.crud.task import celery_task_log as crud_celery_log
from app.models.task import Task, StudentTask
from app.crud.ecs import ecs_instance

logger = logging.getLogger(__name__)


def create_ecs_instance(student_task_id: int, task_id: int, instance_name: str) -> Dict[str, Any]:
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
                celery_task_id=task_id,
                status="FAILURE",
                result=error_msg
            )
            student_task.update_status(db, student_task_id=student_task_id, status="Error")
            ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Error")
            return {"success": False, "error": error_msg}

        # 获取任务配置信息
        task_obj = db.query(Task).filter(Task.id == student_task_obj.task_id).first()
        if not task_obj:
            error_msg = f"Task with id {student_task_obj.task_id} not found"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=task_id,
                status="FAILURE",
                result=error_msg
            )
            student_task.update_status(db, student_task_id=student_task_id, status="Error")
            ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Error")
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

        # 获取任务对应的环境信息
        env_template = db.query(EnvironmentTemplate).filter(EnvironmentTemplate.id == task_obj.environment_id).first()
        if not env_template:
            error_msg = f"Environment template with id {task_obj.environment_id} not found"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=task_id,
                status="FAILURE",
                result=error_msg
            )
            student_task.update_status(db, student_task_id=student_task_id, status="Error")
            ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Error")
            return {"success": False, "error": error_msg}
        # 如果提供了多组实例类型、安全组、VSwitch，则随机选择一组
        # 必须要一一对应
        resource_config = env_template.resource_config
        min_index = 99999

        instance_types=resource_config.get("instance_type", None)
        security_group_ids=resource_config.get("security_group_id", None)
        vswitch_ids=resource_config.get("vswitch_id", None)

        if not instance_types or not security_group_ids or not vswitch_ids:
            error_msg = f"Environment template with id {task_obj.environment_id} resource_config error"
            crud_celery_log.update_status(
                db=db,
                celery_task_id=task_id,
                status="FAILURE",
                result=error_msg
            )
            student_task.update_status(db, student_task_id=student_task_id, status="Error")
            ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Error")
            return {"success": False, "error": error_msg}

        if ',' in instance_types:
            instance_types = instance_types.split(',')
            if len(instance_types)<min_index:
                min_index = len(instance_types)
        if ',' in security_group_ids:
            security_group_ids = security_group_ids.split(',')
            if len(security_group_ids)<min_index:
                min_index = len(security_group_ids)
        if ',' in vswitch_ids:
            vswitch_ids = vswitch_ids.split(',')
            if len(vswitch_ids)<min_index:
                min_index = len(vswitch_ids)

        if min_index != 99999:
            random_index=random.Random().randint(0,min_index-1)
            c_instance_type=instance_types[random_index]
            c_security_group_id=security_group_ids[random_index]
            c_vswitch_id=vswitch_ids[random_index]
        else:
            c_instance_type=instance_types
            c_security_group_id=security_group_ids
            c_vswitch_id=vswitch_ids

        # 检查密码，如果为空则随机生成
        password = resource_config.get("password", None)
        if not password or password.strip() == '':
            password = f"R2p{uuid.uuid4().hex[:10]}!"


        # 调用阿里云SDK创建ECS实例
        result = ali_cloud_service.create_ecs_instance(
            region_id=resource_config.get("region_id", "cn-hangzhou"),
            image_id=env_template.image,
            instance_type=c_instance_type,
            security_group_id=c_security_group_id,
            vswitch_id=c_vswitch_id,
            internet_max_bandwidth_out=resource_config.get("internet_max_bandwidth_out",0),
            spot_strategy=resource_config.get("spot_strategy", None),
            password=password,
            auto_release_time=auto_release_time,
            custom_params=resource_config.get("custom_params",None)
        )

        if not result["success"]:
            crud_celery_log.update_status(
                db=db,
                celery_task_id=task_id,
                status="FAILURE",
                result=json.dumps({"error": result["error"]})
            )

            # 更新学生任务状态
            student_task.update_status(db, student_task_id=student_task_id, status="Error")
            ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Error")

            return {"success": False, "error": result["error"]}

        # 如果成功，更新学生任务记录
        instance_id = result["instance_ids"][0] if result["instance_ids"] else None
        if instance_id:
            ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Pending", instance_id=instance_id, password=password)
            student_task.update_status(db, student_task_id=student_task_id, status="Starting")

        crud_celery_log.update_status(
            db=db,
            celery_task_id=task_id,
            status="SUCCESS",
            result=json.dumps(result)
        )

        return {"success": True, "result": result}

    except Exception as e:
        logger.exception("Error creating ECS instance")
        crud_celery_log.update_status(
            db=db,
            celery_task_id=task_id,
            status="FAILURE",
            result=str(e)
        )
        ecs_instance.update_status_by_instance_name(db=db, instance_name=instance_name, status="Error")
        student_task.update_status(db, student_task_id=student_task_id, status="Error")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def delete_instance(student_task_id: int,task_id: int,ecs_instance_model:ECSInstance) -> Dict[str, Any]:
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
                celery_task_id=student_task_id,
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
                celery_task_id=student_task_id,
                status="FAILURE",
                result=error_msg
            )
            return {"success": False, "error": error_msg}



        # 调用阿里云SDK删除ECS实例
        result = ali_cloud_service.delete_instance(
            region_id=ecs_instance_model.region_id,
            instance_id=ecs_instance_model.instance_id,
            force=True
        )

        # 无论删除成功与否，都更新任务状态
        student_task_obj.status = "Stopped"
        student_task_obj.end_at = datetime.datetime.utcnow()
        db.add(student_task_obj)
        db.commit()

        if not result["success"]:
            crud_celery_log.update_status(
                db=db,
                celery_task_id=student_task_id,
                status="FAILURE",
                result=json.dumps({"error": result["error"]})
            )
            return {"success": False, "error": result["error"]}

        crud_celery_log.update_status(
            db=db,
            celery_task_id=student_task_id,
            status="SUCCESS",
            result=json.dumps(result)
        )
        ecs_instance.update_status(db=db,instance_id=ecs_instance_model.instance_id,status="Stopped")

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


@celery_app.task(name="app.tasks.ecs_tasks.check_instance_status")
def check_instance_status() -> Dict[str, Any]:
    """检查实例状态任务"""
    db = SessionLocal()
    try:
        # 获取所有活跃的实例
        active_instances = ecs_instance.get_active_instances(db=db)
        if not active_instances:
            return {"success": True, "message": "No active instances found"}

        # 按region分组处理，每次最多处理100个实例
        region_instances = {}
        for instance in active_instances:
            if not instance.instance_id:
                continue


            region_id = instance.region_id
            if region_id not in region_instances:
                region_instances[region_id] = []

            region_instances[region_id].append({
                "instance_id": instance.instance_id,
                "id": instance.id
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
                    #id = instance["id"]

                    if instance_id in instance_info.keys():
                        info = instance_info[instance_id]
                        ecs_instance.update_status(db=db,instance_id=instance_id, status=info["Status"],
                            private_ip=info["VpcAttributes"]["PrivateIpAddress"]["IpAddress"][0] if len(info["VpcAttributes"]["PrivateIpAddress"]["IpAddress"])>0 else None,
                            public_ip=info["PublicIpAddress"]["IpAddress"][0] if len(info["PublicIpAddress"]["IpAddress"])>0 else None)
                        crud_student_task.update_status(
                            db=db,
                            student_task_id=next((inst.student_task_id for inst in active_instances if inst.instance_id == instance_id), None),
                            status="Running",

                        )
                    else:
                        if next((inst.status for inst in active_instances if
                                                  inst.instance_id == instance_id), None) == "Running":
                            ecs_instance.update_status(db=db,instance_id=instance_id,status="Stopped")
                        crud_student_task.update_status(
                            db=db,
                            student_task_id=next((inst.student_task_id for inst in active_instances if
                                                  inst.instance_id == instance_id), None),
                            status="Stopped"
                        )

        return {"success": True}

    except Exception as e:
        logger.exception("Error checking instance status")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.ecs_tasks.create_ecs_instance_task")
def create_ecs_instance_task(
        student_task_id: int,
        instance_name: str = None
):
    """Celery任务：创建ECS实例"""
    # 获取task_id
    db = SessionLocal()
    try:
        student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
        if not student_task:
            logger.error(f"Student task not found: {student_task_id}")
            return {"status": "error", "message": "Student task not found"}

        task_id = student_task.task_id
    finally:
        db.close()

    # 调用原函数创建实例
    return create_ecs_instance(student_task_id=student_task_id, task_id=task_id, instance_name=instance_name)


@celery_app.task(name="app.tasks.ecs_tasks.stop_ecs_instance_task")
def stop_ecs_instance_task(instance_id: str):
    """Celery任务：停止并释放ECS实例"""
    # 获取student_task_id和task_id
    db = SessionLocal()
    try:
        #student_task = db.query(ecs_instance).filter(StudentTask.ecs_instance_id == instance_id).first()
        ecs = ecs_instance.get_by_instance_id(db=db, instance_id=instance_id)
        student_task = db.query(StudentTask).get(ecs.student_task_id)
        if not student_task:
            logger.error(f"No student task found for instance {instance_id}")
            return {"status": "error", "message": "Student task not found"}

        student_task_id = student_task.id
        task_id = student_task.task_id
    finally:
        db.close()

    # 调用原函数删除实例
    return delete_instance(student_task_id=student_task_id, task_id=task_id, ecs_instance_model=ecs)