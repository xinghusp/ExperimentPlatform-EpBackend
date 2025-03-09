import socket
import asyncio
import logging
from typing import Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class GuacamoleService:
    """
    Guacamole 服务，处理远程桌面连接
    """
    def __init__(self):
        self.host = settings.GUACAMOLE_HOST
        self.port = settings.GUACAMOLE_PORT
    
    async def create_tunnel(
        self, protocol: str, hostname: str, port: int, username: str, password: str, 
        width: int = 1024, height: int = 768
    ) -> Dict:
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
            
        Returns:
            Dict: 包含连接信息的字典
        """
        try:
            # 创建 guacd 连接
            reader, writer = await asyncio.open_connection(self.host, self.port)
            
            # 构建连接参数
            connection_params = {
                "protocol": protocol,
                "hostname": hostname,
                "port": str(port),
                "username": username,
                "password": password,
                "width": str(width),
                "height": str(height),
                "image_encoding": "png",  # 图像编码
                "color_depth": "16",  # 颜色深度
                "png_compression": "9",  # PNG压缩级别
                "frame_rate": "15",  # 帧率
                "security": "any",  # RDP安全模式
                "ignore-cert": "true"  # 忽略证书验证
            }
            
            # 发送选择协议命令
            protocol_command = f"select,{len(protocol)}.{protocol}"
            writer.write(protocol_command.encode() + b';')
            await writer.drain()
            
            # 接收服务器响应
            response = await reader.readuntil(b';')
            
            # 发送连接参数
            for key, value in connection_params.items():
                if key == "protocol":
                    continue
                param_command = f"{key},{len(value)}.{value}"
                writer.write(param_command.encode() + b';')
                await writer.drain()
            
            # 发送连接命令结束符
            writer.write(b"connect,0.;")
            await writer.drain()
            
            # 读取连接ID
            connect_response = await reader.readuntil(b';')
            connection_id = connect_response.decode().split(',')[0]
            
            writer.close()
            await writer.wait_closed()
            
            return {
                "success": True,
                "connection_id": connection_id,
                "params": connection_params
            }
            
        except Exception as e:
            logger.error(f"Error creating Guacamole tunnel: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


guacamole_service = GuacamoleService()