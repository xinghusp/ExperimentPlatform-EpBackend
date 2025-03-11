import logging
import asyncio
import uuid
from typing import Dict, Any, Optional

from guacamole.client import GuacamoleClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class GuacamoleService:
    """
    使用 pyguacamole 库实现的 Guacamole 服务
    专注于握手后的忠实数据转发
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
        创建与 guacd 的连接隧道并完成握手

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
            logger.info(f"尝试连接 guacd 服务器 {self.host}:{self.port} -> {hostname}:{port} (协议: {protocol})")

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
                "dpi": dpi,
                "image": ["image/png","image/jpeg"],
                "audio": ["audio/ogg", "audio/mp3", "audio/aac"]
                # "video": ["video/h264", "video/webm"]

            }

            # 添加其他参数
            connection_params.update(kwargs)

            # 创建 GuacamoleClient 实例
            client = GuacamoleClient(self.host, self.port, timeout=10)

            # 在单独的线程中执行连接和握手
            def connect_and_handshake():
                try:

                    # 执行协议握手
                    handshake_result = client.handshake(
                        protocol=protocol,
                        **connection_params
                    )

                    logger.info(f"Guacamole握手成功: {connection_id}")
                    return True, handshake_result
                except Exception as e:
                    logger.exception(f"Guacamole连接或握手失败: {e}")
                    try:
                        client.close()
                    except:
                        pass
                    return False, str(e)

            # 在事件循环中执行阻塞操作
            loop = asyncio.get_event_loop()
            success, result = await loop.run_in_executor(None, connect_and_handshake)

            if not success:
                return {"success": False, "error": f"连接或握手失败: {result}"}

            # 存储客户端对象和参数
            self.connections[connection_id] = {
                "client": client,
                "protocol": protocol,
                "params": connection_params,
                "active": True
            }

            logger.info(f"成功创建 Guacamole 连接: {connection_id}, 协议: {protocol}")
            return {
                "success": True,
                "connection_id": connection_id
            }

        except Exception as e:
            logger.exception(f"创建 Guacamole 连接失败: {e}")
            return {"success": False, "error": str(e)}

    async def read_instruction(self, connection_id: str) -> Optional[str]:
        """
        从Guacamole服务器读取指令数据，返回原始字符串

        Args:
            connection_id: 连接标识符

        Returns:
            Optional[str]: 接收到的原始指令字符串，或者None表示无数据或出错
        """
        if connection_id not in self.connections:
            return None

        conn_data = self.connections[connection_id]
        if not conn_data.get("active", False):
            return None

        client = conn_data["client"]
        loop = asyncio.get_event_loop()

        try:
            # 在线程池中非阻塞地接收数据
            def receive_data():
                try:
                    # 直接返回原始指令字符串
                    return client.receive()
                except Exception as e:
                    if "timed out" in str(e).lower():
                        # 超时是正常的，返回None
                        return None
                    # 其他错误记录并返回None
                    logger.debug(f"接收数据时出错: {e}")
                    return None

            # 执行接收操作
            instruction = await loop.run_in_executor(None, receive_data)
            return instruction

        except Exception as e:
            logger.error(f"读取指令时出错: {e}")
            return None

    async def send_instruction(self, connection_id: str, instruction: str) -> bool:
        """
        发送原始指令字符串到Guacamole服务器

        Args:
            connection_id: 连接标识符
            instruction: 原始指令字符串

        Returns:
            bool: 是否发送成功
        """
        if connection_id not in self.connections:
            logger.warning(f"发送指令失败: 未找到连接 {connection_id}")
            return False

        conn_data = self.connections[connection_id]
        if not conn_data.get("active", False):
            logger.warning(f"发送指令失败: 连接 {connection_id} 不活跃")
            return False

        client = conn_data["client"]
        loop = asyncio.get_event_loop()

        try:
            # 在线程池中执行发送操作
            def send_data():
                try:
                    client.send(instruction)
                    return True
                except Exception as e:
                    logger.error(f"发送指令时出错: {e}")
                    return False

            return await loop.run_in_executor(None, send_data)
        except Exception as e:
            logger.error(f"发送指令时出错: {e}")
            return False

    async def close_tunnel(self, connection_id: str) -> bool:
        """
        关闭连接隧道

        Args:
            connection_id: 连接标识符

        Returns:
            bool: 是否关闭成功
        """
        if connection_id not in self.connections:
            logger.warning(f"关闭连接失败: 未找到连接 {connection_id}")
            return False

        conn_data = self.connections[connection_id]
        client = conn_data["client"]

        # 标记连接为非活跃
        conn_data["active"] = False

        try:
            # 在线程池中执行关闭操作
            def close_connection():
                try:
                    # 尝试发送断开连接指令
                    try:
                        client.send("disconnect;")
                    except:
                        pass

                    # 关闭连接
                    client.close()
                    return True
                except Exception as e:
                    logger.error(f"关闭连接时出错: {e}")
                    return False

            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, close_connection)

            # 无论关闭是否成功，都从连接字典中移除
            if connection_id in self.connections:
                del self.connections[connection_id]

            logger.info(f"已关闭连接: {connection_id}")
            return success
        except Exception as e:
            logger.exception(f"关闭连接时出错: {e}")

            # 确保连接从字典中移除
            if connection_id in self.connections:
                del self.connections[connection_id]

            return False


# 单例实例
guacamole_service = GuacamoleService()