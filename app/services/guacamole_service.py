import logging
import hashlib
import time
import base64
import hmac
import uuid
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_credentials(connection_id: str, protocol: str = "rdp") -> Dict[str, Any]:
    """生成Guacamole连接凭据"""
    try:
        # 生成简单的认证令牌（在实际环境中应使用更安全的方法）
        timestamp = str(int(time.time()))
        random_id = str(uuid.uuid4())

        # 创建签名
        message = f"{connection_id}:{timestamp}:{random_id}"
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # 创建认证令牌
        auth_token = base64.b64encode(
            f"{connection_id}:{timestamp}:{random_id}:{signature}".encode()
        ).decode()

        return {
            "auth_token": auth_token,
            "protocol": protocol,
            "timestamp": timestamp
        }

    except Exception as e:
        logger.error(f"Failed to generate Guacamole credentials: {e}")
        raise