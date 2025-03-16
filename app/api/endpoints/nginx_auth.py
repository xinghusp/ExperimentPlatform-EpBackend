
from fastapi import APIRouter, Response, Request, Cookie, Depends
from typing import Optional
import json
import logging
import redis
from app.core.config import settings

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

# 创建Redis客户端
redis_client = redis.Redis.from_url(
    settings.CELERY_BROKER_URL,
    encoding="utf-8",
    decode_responses=True
)


@router.get("/jupyter")
async def jupyter(
        response: Response,
        jupyter_token: Optional[str] = Cookie(None)
):
    """
    Jupyter认证端点，用于Nginx auth_request
    使用cookie中的access_token进行认证
    """
    try:
        # 验证访问令牌
        if not jupyter_token:
            logger.warning("No access token in cookie")
            return Response(status_code=401)

        # 从Redis获取容器信息
        redis_key = f"jc:{jupyter_token}"
        container_data = redis_client.get(redis_key)

        if not container_data:
            logger.warning(f"No container data found for token:{jupyter_token}")
            return Response(status_code=401)

        container_info = json.loads(container_data)

        # 设置响应头，供Nginx使用
        response.headers["X-Jupyter-Port"] = container_info["port"]
        response.headers["X-Jupyter-Host"] = container_info["host"]
        response.headers["X-Jupyter-Container-Id"] = container_info["container_id"]
        response.headers["X-Jupyter-Container-Name"] = container_info["name"]

        return Response(status_code=200)

    except Exception as e:
        logger.exception(f"Error during authentication: {str(e)}")
        return Response(status_code=500)