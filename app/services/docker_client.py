import logging
import docker
from typing import Dict, Any
from docker.errors import DockerException

from app.core.config import settings

logger = logging.getLogger(__name__)
client = docker.from_env()


def create_container(
        image: str,
        container_name: str,
        memory: str = "1g",
        cpu: str = "1",
        memory_limit: str = "2g",
        cpu_limit: str = "2"
) -> Dict[str, Any]:
    """
    创建并启动Docker容器
    """
    try:
        # 转换资源限制格式
        mem_limit = memory if "g" in memory.lower() else f"{memory}m"

        # 创建并启动容器
        container = client.containers.run(
            image=image,
            name=container_name,
            detach=True,
            environment={
                "JUPYTER_TOKEN": "none"  # 禁用Jupyter自己的token认证
            },
            mem_limit=mem_limit,
            cpus=float(cpu_limit),
            ports={'8888/tcp': None},  # 自动分配端口
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 3}
        )

        # 获取容器信息
        container.reload()

        # 获取映射的端口
        port_bindings = container.attrs['NetworkSettings']['Ports']['8888/tcp']
        host_port = port_bindings[0]['HostPort'] if port_bindings else '8888'
        host_ip = settings.DOCKER_HOST_IP or "localhost"

        return {
            "id": container.id,
            "name": container.name,
            "host": host_ip,
            "port": int(host_port),
            "url": f"http://{host_ip}:{host_port}",
            "status": "running"
        }

    except Exception as e:
        logger.error(f"Failed to create container: {e}")
        raise


def stop_container(container_id: str) -> bool:
    """
    停止并删除Docker容器
    """
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=10)
        container.remove()
        return True
    except DockerException as e:
        logger.error(f"Failed to stop container {container_id}: {e}")
        return False