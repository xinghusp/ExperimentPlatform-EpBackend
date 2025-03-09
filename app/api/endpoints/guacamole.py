from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import HTMLResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from typing import Dict

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


@router.websocket("/ws/{student_task_id}")
async def guacamole_ws(websocket: WebSocket, student_task_id: int, db: Session = Depends(get_db)):
    """
    WebSocket连接处理Guacamole通信
    """
    await websocket.accept()
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

        # 创建与Guacamole服务器的连接
        tunnel_result = await guacamole_service.create_tunnel(
            protocol="rdp",
            hostname=student_task.ecs_ip_address,
            port=3389,
            username="Administrator",
            password=task.password,
            width=1920,
            height=1080,
            dpi=96,
            security="any",
            ignore_cert="true",
            enable_wallpaper="false",
            enable_theming="true",
            enable_font_smoothing="true",
            enable_full_window_drag="false",
            enable_desktop_composition="false",
            enable_menu_animations="false"
        )
        print("tunnel_result:", tunnel_result)
        if not tunnel_result["success"]:
            await websocket.close(code=1011, reason=f"无法创建远程桌面连接: {tunnel_result.get('error')}")
            return

        connection_id = tunnel_result["connection_id"]

        # 启动数据转发任务 - 从GuacamoleService获取数据并发送到WebSocket
        async def tunnel_message_forwarder():
            try:
                while True:
                    instruction = await guacamole_service.read_instruction(connection_id)
                    logger.info(f"收到指令: {instruction}")
                    if instruction:
                        # 转换为Guacamole协议字符串
                        # message = ""
                        # for i, element in enumerate(instruction):
                        #     message += str(len(element)) + "." + element
                        #     if i < len(instruction) - 1:
                        #         message += ","
                        #     else:
                        #         message += ";"

                        await websocket.send_text(instruction)
                    else:
                        # 如果没有数据，短暂等待
                        await asyncio.sleep(0.01)
            except Exception as e:
                logger.exception(f"转发数据时出错: {e}")

        # 启动转发任务
        tunnel_task = asyncio.create_task(tunnel_message_forwarder())

        # 向客户端发送连接成功消息
        # await websocket.send_json({
        #     "type": "connect",
        #     "connectionId": connection_id
        # })

        # 处理从客户端发来的消息
        while True:
            message = await websocket.receive()
            logger.info(f"收到WebSocket消息: {message}")

            if "text" in message:
                text = message["text"]

                # 尝试解析JSON消息
                try:
                    data = json.loads(text)
                    msg_type = data.get("type")
                    msg_text = data.get("text")
                    await guacamole_service.send_instruction(connection_id, msg_text)

                    # if msg_type == "mouse":
                    #     await guacamole_service.send_mouse(
                    #         connection_id,
                    #         data.get("x"), data.get("y"),
                    #         data.get("left"), data.get("middle"), data.get("right")
                    #     )
                    # elif msg_type == "key":
                    #     await guacamole_service.send_key(
                    #         connection_id,
                    #         data.get("pressed"), data.get("keysym")
                    #     )
                    # elif msg_type == "size":
                    #     await guacamole_service.resize(
                    #         connection_id,
                    #         data.get("width"), data.get("height")
                    #     )
                except json.JSONDecodeError:
                    # 不是JSON，可能是原始Guacamole指令
                    await guacamole_service.send_instruction(connection_id, text)

    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {student_task_id}")
    except Exception as e:
        logger.exception(f"WebSocket处理异常: {e}")
    finally:
        # 取消转发任务
        if tunnel_task and not tunnel_task.done():
            tunnel_task.cancel()
            try:
                await tunnel_task
            except asyncio.CancelledError:
                pass

        # 关闭Guacamole连接
        if connection_id:
            await guacamole_service.close_tunnel(connection_id)