import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, List

from guacamole.client import GuacamoleClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class GuacamoleService:
    """
    使用 pyguacamole 库实现的 Guacamole 服务
    """

    def __init__(self):
        self.host = settings.GUACAMOLE_HOST
        self.port = settings.GUACAMOLE_PORT
        self.connections = {}  # 存储活跃连接
        self.tasks = {}  # 存储维护连接的任务

    async def create_tunnel(
            self, protocol: str, hostname: str, port: int, username: str, password: str,
            width: int = 1024, height: int = 768, dpi: int = 96, **kwargs
    ) -> Dict[str, Any]:
        """
        创建与 guacd 的连接隧道

        Args:
            protocol: 远程桌面协议 (rdp, vnc, ssh)
            hostname: 远程主机名或IP
            port: 远程主机端口
            username: 登录用户名
            password: 登录密码
            width: 屏幕宽度
            height: 屏幕高度
            dpi: 屏幕DPI
            **kwargs: 其他协议特定参数

        Returns:
            Dict: 包含连接信息的字典
        """
        try:
            logger.info(f"尝试连接 guacd 服务器 {self.host}:{self.port}")

            # 生成唯一连接ID
            connection_id = str(uuid.uuid4())

            # 创建参数字典
            connection_params = {
                "hostname": hostname,
                "port": port,
                "username": username,
                "password": password,
                "width": width,
                "height": height,
                "dpi": dpi
            }

            # 添加其他参数
            connection_params.update(kwargs)

            # 创建 GuacamoleClient 实例
            client = GuacamoleClient(self.host, self.port, timeout=20)

            # 在单独的协程中运行连接过程
            def connect_sync():
                try:
                    # 连接到服务器并握手
                    client.handshake(protocol=protocol, **connection_params)
                    return True
                except Exception as e:
                    logger.exception(f"Guacamole连接失败: {e}")
                    return False

            # 在线程池中执行阻塞操作
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, connect_sync)

            if not success:
                logger.error("无法建立 Guacamole 连接")
                return {"success": False, "error": "连接握手失败"}

            # 存储客户端对象
            self.connections[connection_id] = {
                "client": client,
                "params": connection_params
            }

            # 启动接收消息的任务
            self.tasks[connection_id] = asyncio.create_task(
                self._maintain_connection(connection_id, client)
            )

            logger.info(f"成功创建 Guacamole 连接: {connection_id}")
            return {
                "success": True,
                "connection_id": connection_id,
                "params": connection_params
            }

        except Exception as e:
            logger.exception(f"创建 Guacamole 连接失败: {e}")
            return {"success": False, "error": str(e)}

    async def _maintain_connection(self, connection_id: str, client: GuacamoleClient):
        """维持连接活跃的后台任务"""
        try:
            while True:
                # 在线程池中执行读取操作
                loop = asyncio.get_event_loop()

                def receive_message():
                    try:
                        # 非阻塞接收消息，超时返回None
                        return client.receive(timeout=1.0)
                    except Exception as e:
                        if "timeout" in str(e).lower():
                            # 超时正常，继续循环
                            return None
                        # 其他错误抛出
                        raise

                try:
                    # 在线程池中执行接收操作
                    instruction = await loop.run_in_executor(None, receive_message)

                    if instruction:
                        opcode = instruction.opcode
                        if opcode == "nop":
                            # 收到心跳包，回复心跳
                            await loop.run_in_executor(None, lambda: client.send("nop"))
                        elif opcode == "disconnect":
                            # 服务器要求断开
                            logger.info(f"服务器请求断开连接: {connection_id}")
                            break
                        elif opcode == "error":
                            # 服务器报告错误
                            args = instruction.args
                            error_msg = args[0] if args else "未知错误"
                            logger.error(f"Guacamole服务器报告错误: {error_msg}")
                            break
                except Exception as e:
                    if "closed" in str(e).lower() or "eof" in str(e).lower():
                        # 连接已关闭
                        logger.info(f"Guacamole连接已关闭: {connection_id}")
                        break
                    else:
                        logger.exception(f"接收消息时出错: {e}")
                        break

                # 短暂休息避免CPU使用率过高
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"连接维护任务被取消: {connection_id}")
        except Exception as e:
            logger.exception(f"连接维护过程中出错: {e}")
        finally:
            # 确保连接被清理
            await self.close_tunnel(connection_id)

    async def send_mouse(self, connection_id: str, x: int, y: int,
                         left: bool = False, middle: bool = False,
                         right: bool = False) -> bool:
        """发送鼠标事件"""
        try:
            if connection_id not in self.connections:
                logger.warning(f"未找到连接: {connection_id}")
                return False

            conn_data = self.connections[connection_id]
            client = conn_data["client"]

            # 计算鼠标按钮状态
            button_mask = 0
            if left:
                button_mask |= 1
            if middle:
                button_mask |= 2
            if right:
                button_mask |= 4

            # 在线程池中执行发送操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.send("mouse", x, y, button_mask)
            )
            return True

        except Exception as e:
            logger.error(f"发送鼠标事件失败: {e}")
            return False

    async def send_key(self, connection_id: str, pressed: int, keysym: int) -> bool:
        """发送键盘事件"""
        try:
            if connection_id not in self.connections:
                logger.warning(f"未找到连接: {connection_id}")
                return False

            conn_data = self.connections[connection_id]
            client = conn_data["client"]

            # 在线程池中执行发送操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.send("key", pressed, keysym)
            )
            return True

        except Exception as e:
            logger.error(f"发送键盘事件失败: {e}")
            return False

    async def resize(self, connection_id: str, width: int, height: int) -> bool:
        """调整屏幕大小"""
        try:
            if connection_id not in self.connections:
                logger.warning(f"未找到连接: {connection_id}")
                return False

            conn_data = self.connections[connection_id]
            client = conn_data["client"]

            # 在线程池中执行发送操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.send(f"4.size,1.0,4.{width},3.{height}")  # 96是DPI
            )
            return True

        except Exception as e:
            logger.error(f"调整屏幕大小失败: {e}")
            return False

    async def close_tunnel(self, connection_id: str) -> bool:
        """关闭连接隧道"""
        try:
            if connection_id not in self.connections:
                logger.warning(f"未找到连接: {connection_id}")
                return False

            # 取消维护任务
            if connection_id in self.tasks:
                task = self.tasks[connection_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.tasks[connection_id]

            # 获取客户端对象
            conn_data = self.connections.get(connection_id)
            if conn_data:
                client = conn_data["client"]

                # 在线程池中执行关闭操作
                loop = asyncio.get_event_loop()

                def close_client():
                    try:
                        # 发送断开连接指令
                        client.send("disconnect")
                    except:
                        pass

                    # 关闭客户端
                    try:
                        client.close()
                    except:
                        pass

                await loop.run_in_executor(None, close_client)

                # 移除连接
                del self.connections[connection_id]

            logger.info(f"已关闭连接: {connection_id}")
            return True

        except Exception as e:
            logger.error(f"关闭连接失败: {e}")
            return False


    async def read_instruction(self, connection_id: str) -> Optional[List[str]]:
        """读取一条指令"""
        if connection_id not in self.connections:
            return None

        conn_data = self.connections[connection_id]
        client = conn_data["client"]

        loop = asyncio.get_event_loop()

        def receive_data():
            #try:
                # 非阻塞方式读取消息
            return client.receive()
            #except:
                #return None

        # 在线程池中执行接收操作
        instruction = await loop.run_in_executor(None, receive_data)
        return instruction
        # if instruction:
        #     return [instruction.opcode] + list(instruction.args)
        # return None


    async def send_instruction(self, connection_id: str, instruction: str) -> bool:
        """发送原始指令"""
        if connection_id not in self.connections:
            return False

        conn_data = self.connections[connection_id]
        client = conn_data["client"]

        loop = asyncio.get_event_loop()

        def send_data():
            try:
                client._send_raw(instruction)
                return True
            except:
                return False

        # 在线程池中执行发送操作
        return await loop.run_in_executor(None, send_data)

guacamole_service = GuacamoleService()