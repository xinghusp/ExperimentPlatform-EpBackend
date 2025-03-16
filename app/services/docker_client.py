import logging
import platform
import os
from typing import Dict, Any, Optional

from docker import DockerClient

from app.core.config import settings

logger = logging.getLogger(__name__)

# 延迟导入Docker客户端
docker_client:DockerClient = None
docker_available = False


def init_docker_client():
    """初始化Docker客户端并返回连接状态"""
    global docker_client, docker_available

    try:
        import docker
        from docker.errors import DockerException

        # 连接参数
        client_kwargs = {}

        # 优先使用配置中的DOCKER_HOST
        if settings.DOCKER_HOST:
            client_kwargs["base_url"] = settings.DOCKER_HOST
            logger.info(f"使用配置的Docker主机: {settings.DOCKER_HOST}")

            # 如果启用了TLS验证
            if settings.DOCKER_TLS_VERIFY:
                client_kwargs["tls"] = docker.tls.TLSConfig(
                    verify=True,
                    cert_path=settings.DOCKER_CERT_PATH,
                    assert_hostname=False
                )
                logger.info("Docker TLS验证已启用")

        try:
            client = docker.DockerClient(**client_kwargs)
            # 测试连接
            client.ping()
            docker_client = client
            docker_available = True
            logger.info("成功连接到Docker引擎")
            return True
        except DockerException as e:
            logger.warning(f"无法连接到Docker引擎: {str(e)}")
            docker_client = None
            docker_available = False
            return False
    except ImportError:
        logger.warning("未安装Docker SDK，Jupyter容器功能将不可用")
        return False


# 尝试初始化Docker客户端
init_docker_client()


def is_docker_available() -> bool:
    """检查Docker是否可用"""
    return docker_available


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
    if not docker_available:
        error_msg = "Docker引擎不可用，无法创建容器"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        # 转换资源限制格式
        mem_limit = str(memory) if "g" in str(memory).lower() else f"{memory}m"

        # 创建并启动容器
        container = docker_client.containers.run(
            image=image,
            name=container_name,
            detach=True,
            environment={
                "JUPYTER_TOKEN": "none"  # 禁用Jupyter自己的token认证
            },
            mem_limit=mem_limit,
            nano_cpus=int(float(cpu_limit) * 1e9),  # Convert CPU cores to nano CPUs
            ports={'8888/tcp': None},  # 自动分配端口
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 3}
        )

        # 获取容器信息
        container.reload()

        # 获取映射的端口
        port_bindings = container.attrs['NetworkSettings']['Ports'].get('8888/tcp')
        if port_bindings:
            host_port = port_bindings[0]['HostPort']
        else:
            logger.warning(f"无法获取容器 {container.id} 的端口映射，使用默认端口8888")
            host_port = '8888'

        # 使用配置的Docker主机IP
        host_ip = settings.DOCKER_HOST_IP

        return {
            "id": container.id,
            "name": container.name,
            "host": host_ip,
            "port": int(host_port),
            "url": f"http://{host_ip}:{host_port}",
            "status": "running"
        }

    except Exception as e:
        logger.error(f"创建容器失败: {e}")
        raise


def stop_container(container_id: str) -> bool:
    """
    停止并删除Docker容器
    """
    if not docker_available:
        logger.warning(f"Docker引擎不可用，无法停止容器 {container_id}")
        return False

    try:
        from docker.errors import DockerException, NotFound

        try:
            container = docker_client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove()
            logger.info(f"容器 {container_id} 已停止并删除")
            return True
        except NotFound:
            logger.warning(f"容器 {container_id} 不存在")
            return True  # 返回True因为容器已不存在，视为成功

    except DockerException as e:
        logger.error(f"停止容器 {container_id} 失败: {e}")
        return False