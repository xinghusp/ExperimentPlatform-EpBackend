from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import HTMLResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from typing import Dict, List, Optional

from app.api.deps import get_db, get_current_student
from app.core.config import settings
from app.core.templates import templates
from app.schemas.task import StudentTask
from app.crud.task import student_task as crud_student_task
from app.services.guacamole import guacamole_service
from app.models.task import Task
from app.models.task import StudentTask as StudentTaskDb, Task as TaskDb

router = APIRouter()
logger = logging.getLogger(__name__)

# 存储WebSocket连接
active_connections: Dict[int, WebSocket] = {}


@router.get("/{student_task_id}", response_class=HTMLResponse)
async def guacamole_client(
        student_task_id: int,
        request: Request,
        db: Session = Depends(get_db),
        token: str = Query(...)
):
    """
    获取Guacamole客户端HTML页面，使用模板文件
    """
    try:
        # 验证临时令牌
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms="HS256"
        )
        expected_sub = f"st_{student_task_id}"

        if payload["sub"] != expected_sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token for this resource"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    student_task = crud_student_task.get(db=db, id=student_task_id)

    if not student_task.ecs_ip_address or student_task.ecs_instance_status != "Running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="实例还未准备好或已停止运行"
        )

    # 获取任务信息
    task = db.query(Task).filter(Task.id == student_task.task_id).first()

    # 计算剩余时间（如果有）
    remaining_time = None
    has_time_limit = False
    if task and task.max_duration and student_task.start_at:
        import datetime
        elapsed = (datetime.datetime.now() - student_task.start_at).total_seconds()
        remaining_seconds = max(0, task.max_duration * 60 - elapsed)
        remaining_time = int(remaining_seconds)
        has_time_limit = True

    # 使用Jinja2模板渲染页面，传递所需的变量
    return templates.TemplateResponse(
        "guacamole/client.html",
        {
            "request": request,
            "student_task_id": student_task_id,
            "has_time_limit": has_time_limit,
            "remaining_time": remaining_time or 0
        }
    )


@router.websocket("/ws/{student_task_id}/{width}/{height}")
async def guacamole_ws(websocket: WebSocket, student_task_id: int, width=1280,height=720,db: Session = Depends(get_db)):
    """
    WebSocket连接处理Guacamole通信
    """
    # 关键修改：接受WebSocket连接时指定子协议为"guacamole"
    if "guacamole" in websocket.headers.get("sec-websocket-protocol", "").split(", "):
        # 客户端请求了guacamole子协议
        await websocket.accept(subprotocol="guacamole")
        logger.info("接受WebSocket连接，子协议: guacamole")
    else:
        # 客户端没有请求子协议，以兼容模式接受
        await websocket.accept()
        logger.info("接受WebSocket连接，无子协议")

    tunnel_task = None
    connection_id = None

    try:
        # 获取学生任务信息
        student_task = db.query(StudentTaskDb).filter_by(id=student_task_id).first()
        if not student_task or not student_task.ecs_ip_address:
            await websocket.close(code=1008, reason="任务不存在或实例未准备好")
            return

        # 获取任务信息
        task = db.query(TaskDb).filter(TaskDb.id == student_task.task_id).first()
        if not task:
            await websocket.close(code=1008, reason="任务信息不存在")
            return

        logger.info(f"创建RDP连接到 {student_task.ecs_ip_address}:3389")

        # 创建与Guacamole服务器的连接
        tunnel_result = await guacamole_service.create_tunnel(
            protocol="rdp",
            hostname=student_task.ecs_ip_address,
            port=3389,
            username="Administrator",
            password=task.password,
            width=int(float(width)),
            height=int(float(height)),
            dpi=96,
            security="any",
            ignore_cert="true",
            enable_wallpaper="false",
            enable_theming="false",
            enable_font_smoothing="false",
            enable_full_window_drag="false",
            enable_desktop_composition="false",
            enable_menu_animations="false",
            color_depth=16,
            disable_audio="true",
            framerate="15"
        )

        if not tunnel_result["success"]:
            error_msg = f"无法创建远程桌面连接: {tunnel_result.get('error')}"
            logger.error(error_msg)
            await websocket.close(code=1011, reason=error_msg)
            return

        connection_id = tunnel_result["connection_id"]
        logger.info(f"成功创建远程桌面连接，ID: {connection_id}")
        await websocket.send_text(f"5.ready,{len(connection_id)+1}.${connection_id};")

        # 启动数据转发任务 - 从GuacamoleService获取数据并发送到WebSocket
        async def tunnel_message_forwarder():
            instruction_count = 0
            try:
                while True:
                    # 从Guacamole服务器读取指令
                    instruction = await guacamole_service.read_instruction(connection_id)
                    if instruction:
                        instruction_count += 1
                        # 每100条日志记录一次，避免日志过多
                        if instruction_count % 100 == 0:
                            logger.debug(f"已转发 {instruction_count} 条指令")

                        # 直接发送原始指令字符串给客户端
                        await websocket.send_text(instruction)
                    else:
                        # 如果没有数据，短暂等待
                        await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                logger.info(f"转发任务已取消，总共转发了 {instruction_count} 条指令")
                raise
            except Exception as e:
                logger.exception(f"转发数据时出错: {e}")

        # 启动转发任务
        tunnel_task = asyncio.create_task(tunnel_message_forwarder())

        # 处理从客户端发来的指令
        while True:
            message = await websocket.receive()

            if "text" in message:
                text = message["text"]
                # 直接将客户端指令发送到Guacamole服务器
                await guacamole_service.send_instruction(connection_id, text)
            elif "bytes" in message:
                # 处理二进制消息
                bytes_data = message["bytes"]
                try:
                    # 将二进制数据转换为文本
                    text = bytes_data.decode("utf-8")
                    await guacamole_service.send_instruction(connection_id, text)
                except UnicodeDecodeError:
                    logger.warning("收到无法解码的二进制数据")

    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {student_task_id}")
    except asyncio.CancelledError:
        logger.info(f"WebSocket处理被取消: {student_task_id}")
    except Exception as e:
        logger.exception(f"WebSocket处理异常: {e}")
    finally:
        # 取消转发任务
        if tunnel_task and not tunnel_task.done():
            tunnel_task.cancel()
            try:
                await tunnel_task
            except asyncio.CancelledError:
                logger.debug("转发任务取消完成")
                pass

        # 关闭Guacamole连接
        if connection_id:
            try:
                close_result = await guacamole_service.close_tunnel(connection_id)
                logger.info(f"关闭Guacamole连接 {connection_id}: {close_result}")
            except Exception as e:
                logger.error(f"关闭Guacamole连接时出错: {e}")