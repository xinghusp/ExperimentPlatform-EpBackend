import logging

from celery import shared_task
from sqlalchemy import text

from app.db.base import SessionLocal
from app.models.task import StudentTask
from app.tasks.ecs_tasks import stop_ecs_instance_task
from app.tasks.jupyter_tasks import stop_jupyter_container_task

logger = logging.getLogger(__name__)

@shared_task()
def cleanup_expired_tasks():
    """
    定时任务：清理超过最大允许时长的实验任务

    检查条件：
    1. 当前时间 > start_at + max_duration(分钟)
    2. 任务状态为 Running
    """
    try:
        db = SessionLocal()
        try:

            # 查询所有超时的任务
            query = """
                SELECT st.id, st.task_type, t.max_duration, 
                    jc.container_id, ei.instance_id
                FROM student_tasks st
                JOIN tasks t ON st.task_id = t.id
                LEFT JOIN jupyter_containers jc ON st.id = jc.student_task_id
                LEFT JOIN ecs_instances ei ON st.id = ei.student_task_id
                WHERE st.status = 'Running'
                    AND st.start_at IS NOT NULL
                    AND t.max_duration IS NOT NULL
                    AND st.start_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL t.max_duration MINUTE)
            """

            # 执行原生SQL查询
            result = db.execute(text(query)).fetchall()

            if not result:
                logger.info("No expired tasks found")
                return

            logger.info(f"Found {len(result)} expired tasks to clean up")

            # 处理每个过期任务
            for row in result:
                student_task_id = row[0]
                task_type = row[1]
                max_duration = row[2]
                container_id = row[3]
                instance_id = row[4]

                logger.info(f"Cleaning up expired task: {student_task_id} (type: {task_type})")

                try:
                    # 根据任务类型调用相应的停止方法
                    if task_type == "jupyter" and container_id:
                        # 启动Jupyter容器停止任务
                        stop_jupyter_container_task.delay(container_id)
                        logger.info(f"Initiated Jupyter container cleanup for task {student_task_id}")

                    elif task_type == "guacamole" and instance_id:
                        # 启动ECS实例停止任务
                        stop_ecs_instance_task.delay(instance_id)
                        logger.info(f"Initiated ECS instance cleanup for task {student_task_id}")

                    else:
                        logger.warning(
                            f"Missing container/instance ID or unknown task type: {task_type} for task {student_task_id}")
                        continue

                    # 更新任务状态为正在停止 (实际的状态更新会在各自的停止任务中完成)
                    # 但我们仍然添加备注说明自动停止的原因
                    student_task = db.query(StudentTask).filter(StudentTask.id == student_task_id).first()
                    if student_task:
                       student_task.status="Stopped"
                    db.add(student_task)

                except Exception as e:
                    logger.exception(f"Error stopping task {student_task_id}: {str(e)}")

            # 提交数据库更改
            db.commit()
            logger.info(f"Successfully processed {len(result)} expired tasks")

        except Exception as e:
            db.rollback()
            logger.exception(f"Error in cleanup_expired_tasks: {str(e)}")
        finally:
            db.close()
    except Exception as e:
        logger.exception(f"Critical error in cleanup_expired_tasks: {str(e)}")