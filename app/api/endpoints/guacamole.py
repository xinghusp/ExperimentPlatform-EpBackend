from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from typing import Dict

from app.api.deps import get_db, get_current_student
from app.core.config import settings
from app.schemas.task import StudentTask
from app.crud.task import student_task as crud_student_task
from app.services.guacamole import guacamole_service
from app.models.task import Task
from app.schemas.task import StudentTask as StudentTaskDb, Task as TaskDb

router = APIRouter()
logger = logging.getLogger(__name__)

# 存储WebSocket连接
active_connections: Dict[int, WebSocket] = {}


@router.get("/{student_task_id}", response_class=HTMLResponse)
async def guacamole_client(
        student_task_id: int,
        db: Session = Depends(get_db), token: str = Query(...)
):
    """
    获取Guacamole客户端HTML页面
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

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>远程桌面实验环境</title>
        <link rel="stylesheet" href="/static/guacamole/guacamole.css">
        <script src="/static/guacamole/guacamole.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #000; }}
            #display {{ position: absolute; width: 100%; height: 100%; }}
            .alert {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                padding: 10px;
                background-color: #f8d7da;
                color: #721c24;
                text-align: center;
                z-index: 1000;
                display: {'block' if has_time_limit else 'none'};
            }}
            .btn-end {{
                position: fixed;
                top: 10px;
                right: 10px;
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                z-index: 1001;
            }}
        </style>
    </head>
    <body>
        <div id="alert" class="alert">
            剩余实验时间: <span id="remaining-time">计算中...</span>
        </div>
        <div id="display"></div>

        <script>
            const studentTaskId = {student_task_id};
            const hasTimeLimit = {str(has_time_limit).lower()};
            const initialRemainingTime = {remaining_time or 0};
            let remainingSeconds = initialRemainingTime;
            const wsUrl = `${{window.location.protocol === 'https:' ? 'wss:' : 'ws:'}}//${{window.location.host}}/api/v1/guacamole/ws/${{studentTaskId}}`;

            // 初始化Guacamole客户端
            let guac = null;

            // 更新剩余时间显示
            function updateRemainingTime() {{
                if (!hasTimeLimit) return;

                const minutes = Math.floor(remainingSeconds / 60);
                const seconds = remainingSeconds % 60;
                document.getElementById('remaining-time').textContent = 
                    `${{minutes.toString().padStart(2, '0')}}:${{seconds.toString().padStart(2, '0')}}`;

                if (remainingSeconds <= 0) {{
                    clearInterval(timerInterval);
                    endExperiment();
                    alert('实验时间已结束，将自动关闭连接');
                }}

                remainingSeconds--;
            }}

            // 心跳检测
            let heartbeatInterval;
            let missedHeartbeats = 0;

            function startHeartbeat() {{
                heartbeatInterval = setInterval(() => {{
                    fetch(`/api/v1/tasks/student/${{studentTaskId}}/heartbeat`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${{localStorage.getItem('token')}}`
                        }}
                    }})
                    .then(response => {{
                        if (!response.ok) throw new Error('心跳检测失败');
                        return response.json();
                    }})
                    .then(data => {{
                        missedHeartbeats = 0;
                    }})
                    .catch(err => {{
                        console.error('心跳错误:', err);
                        missedHeartbeats++;
                        if (missedHeartbeats >= 4) {{
                            clearInterval(heartbeatInterval);
                            endExperiment();
                            alert('连接中断，实验将自动结束');
                        }}
                    }});
                }}, 30000); // 每30秒一次
            }}

           
            // 初始化WebSocket连接
            function connect() {{
                const ws = new WebSocket(wsUrl);

                ws.onopen = function() {{
                    console.log('WebSocket连接已建立');
                }};

                ws.onmessage = function(event) {{
                    const message = JSON.parse(event.data);

                    if (message.type === 'connection') {{
                        // 初始化Guacamole客户端
                        const display = document.getElementById('display');
                        const guacDisplay = document.createElement('div');
                        display.appendChild(guacDisplay);

                        guac = new Guacamole.Client(guacDisplay);

                        // 连接到Guacamole服务器
                        guac.connect(message.connectionString);

                        // 处理鼠标
                        const mouse = new Guacamole.Mouse(guacDisplay);
                        mouse.onmousedown = mouse.onmouseup = mouse.onmousemove = function(mouseState) {{
                            guac.sendMouseState(mouseState);
                        }};

                        // 处理键盘
                        const keyboard = new Guacamole.Keyboard(document);
                        keyboard.onkeydown = function(keysym) {{
                            guac.sendKeyEvent(1, keysym);
                            return false;
                        }};
                        keyboard.onkeyup = function(keysym) {{
                            guac.sendKeyEvent(0, keysym);
                            return false;
                        }};

                        // 启动心跳检测
                        startHeartbeat();

                        // 启动计时器
                        if (hasTimeLimit) {{
                            updateRemainingTime();
                            timerInterval = setInterval(updateRemainingTime, 1000);
                        }}
                    }}
                }};

                ws.onclose = function() {{
                    console.log('WebSocket连接已关闭');
                    if (guac) {{
                        guac.disconnect();
                    }}
                }};

                ws.onerror = function(error) {{
                    console.error('WebSocket错误:', error);
                }};
            }}

            // 开始连接
            connect();

            let timerInterval;
            if (hasTimeLimit) {{
                updateRemainingTime();
                timerInterval = setInterval(updateRemainingTime, 1000);
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.websocket("/ws/{student_task_id}")
async def guacamole_ws(websocket: WebSocket, student_task_id: int, db: Session = Depends(get_db)):
    """
    WebSocket连接处理Guacamole通信
    """
    await websocket.accept()

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
            port=3389,  # RDP默认端口
            username="Administrator",  # Windows默认管理员账号
            password=task.password,
            width=1280,
            height=720
        )

        if not tunnel_result["success"]:
            await websocket.close(code=1011, reason=f"无法创建远程桌面连接: {tunnel_result.get('error')}")
            return

        # 将连接信息发送给客户端
        await websocket.send_json({
            "type": "connection",
            "connectionString": tunnel_result["connection_id"]
        })

        # 存储连接
        active_connections[student_task_id] = websocket

        # 保持连接直到客户端断开
        while True:
            data = await websocket.receive_text()
            # 这里可以实现双向通信

    except WebSocketDisconnect:
        logger.info(f"WebSocket断开: {student_task_id}")
    except Exception as e:
        logger.error(f"WebSocket处理异常: {e}")
    finally:
        if student_task_id in active_connections:
            del active_connections[student_task_id]