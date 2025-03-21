# ExperimentPlatform-EpBackend

**点击访问配套的前端项目：** [ExperimentPlatform-EpFrontend](https://github.com/xinghusp/AssignmentUploadSystem.Frontend)

---

## 项目概述

ExperimentPlatform是一个面向教育领域的实验平台系统，旨在为学生提供远程实验环境。本仓库包含平台的后端API服务，使用Python和FastAPI构建。

该平台支持多种实验环境类型，包括：
- 基于阿里云ECS的远程桌面实验环境
- 基于Docker的Jupyter Notebook实验环境

通过本平台，教师可以基于阿里云或任何标准的Docker环境，为学生准备实验环境。学生端无需安装客户端软件，直接使用网页即可访问实验环境。

## 主要功能

### 用户与权限管理
- 管理员登录与身份验证
- 学生登录与身份验证
- 基于JWT的认证系统
- 多角色权限控制（学生/管理员/超级管理员）

### 班级与学生管理
- 班级创建、修改、删除
- 学生信息管理
- 批量导入学生数据

### 实验任务管理
- 创建不同类型的实验任务（远程桌面/Jupyter）
- 设置实验持续时间与尝试次数限制
- 分配任务到特定班级
- 上传实验附件材料
- 监控实验进度与状态

### 实验环境
1. **远程桌面环境（暂时仅可用于Windows）**
   - 基于Apache Guacamole协议的无客户端远程桌面
   - 自动创建和销毁阿里云ECS实例
   - WebSocket连接实时传输远程桌面操作

2. **Jupyter Notebook环境**
   - 基于Docker容器的Jupyter实验环境


### 系统管理
- 任务监控与强制停止
- 实验环境模板管理
- 资源自动回收与清理

## 技术栈

- **Web框架**: FastAPI
- **ORM**: SQLAlchemy
- **数据库**: MySQL
- **异步任务队列**: Celery + Redis
- **认证**: JWT
- **容器化**: Docker
- **云服务**: 阿里云ECS
- **远程桌面协议**: Apache Guacamole
- **实时通信**: WebSockets

## 开发环境搭建

### 前置条件

- Python 3.8+
- MySQL 5.7+
- Redis
- Docker (用于Jupyter实验)
- Guacamole服务 (用于远程桌面实验)

### 安装步骤

1. 克隆项目:
```bash
git clone https://github.com/xinghusp/ExperimentPlatform-EpBackend.git
cd ExperimentPlatform-EpBackend
```

2. 创建虚拟环境:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. 安装依赖:
```bash
pip install -r requirements.txt
```

4. 配置环境变量:
创建`.env`文件并配置以下变量:
```
MYSQL_SERVER=YOUR_MYSQL_SERVER
MYSQL_USER=YOUR_MYSQL_USER
MYSQL_PASSWORD=YOUR_MYSQL_PASSWORD
MYSQL_DB=YOUR_MYSQL_DB_NAME
ALIYUN_ACCESS_KEY_ID=YOUR_ALIYUN_ACCESS_KEY
ALIYUN_ACCESS_KEY_SECRET=YOUR_ALIYUN_ACCESS_SECRET
CELERY_BROKER_URL=redis://YOUR_REDIS_SERVER/0
CELERY_RESULT_BACKEND=redis://YOUR_REDIS_SERVER/0
GUACAMOLE_HOST=YOUR_GUACAMOLE_HOST_IP
GUACAMOLE_PORT=YOUR_GUACAMOLE_HOST_PORT
ACCESS_TOKEN_EXPIRE_MINUTES=120
SECRET_KEY=YOUR_JWT_ENCRYPT_KEY
DOCKER_HOST=tcp://YOUR_DOCKER_SERVER_API_IP:2375
DOCKER_HOST_IP=YOUR_DOCKER_SERVER_IP

```
请注意Docker需要开放HTTP API
5. 初始化数据库:
```plaintext
请导入数据库样例文件 ExperimentalPlatformDbV2_Example.sql
```

6. 启动应用:
```bash
uvicorn app.main:app --reload
```
生产环境建议使用gunicorn启用多进程。特别是并发用户数大于10人的时候。

7. 启动Celery Worker:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

8. 启动Celery Beat (定时任务):
```bash
celery -A app.core.celery_app beat
```

## 生产环境部署

### Docker部署(待完善)

1. 构建Docker镜像:
```bash
docker build -t experiment-platform-backend .
```

2. 运行容器:
```bash
docker run -d -p 8000:8000 \
  --env-file .env \
  --name ep-backend \
  experiment-platform-backend
```

### Nginx配置示例

```nginx
server {
    listen 80;
    server_name api.your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
}
```

## 系统架构

```
┌────────────┐    ┌─────────────┐    ┌──────────────┐
│  Frontend  │◄───┤  API (FAST) │◄───┤  Database    │
└────────────┘    └─────────────┘    └──────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│ Celery Workers  │         │     Redis       │
└─────────────────┘         └─────────────────┘
          │                           │
┌─────────┴─────────┐       ┌─────────┴─────────┐
▼                   ▼       ▼                   ▼
┌───────────┐  ┌─────────┐  ┌───────────┐  ┌─────────────┐
│ Aliyun    │  │ Docker  │  │ Container │  │ Auth Cache  │
│ ECS API   │  │ API     │  │ Registry  │  │             │
└───────────┘  └─────────┘  └───────────┘  └─────────────┘
```

## API文档

启动服务后，访问 `http://localhost:8000/docs` 获取完整的API文档。

主要API端点:
- `/api/auth/*`: 认证相关
- `/api/admin/*`: 管理员操作
- `/api/students/*`: 学生操作
- `/api/tasks/*`: 实验任务管理
- `/api/classes/*`: 班级管理
- `/api/environments/*`: 环境模板管理

## 定时任务

系统包含以下定时任务:
- 清理过期实验: 自动停止超过最大运行时间的实验
- 资源监控: 监控阿里云ECS实例和Docker容器状态

## 未来计划

1. **系统功能增强**
   - 实验报告提交与批改功能
   - 实验过程录制与回放
   - 学生实验行为数据分析
   - 在线协作功能

2. **技术改进**
   - 多集群实验环境管理
   - 云原生部署支持
   - 支持更多类型的实验环境

3. **扩展性与集成**
   - 第三方教学资源集成
   - 多租户支持

4. **AI助手集成**
    - 帮助学生在遇到问题时可以及时求助

## 贡献指南

1. Fork本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个Pull Request

## 许可证

[MIT License](LICENSE)

## 联系方式

有任何问题或建议，请创建Issue或与项目维护者联系。

---

**项目状态:** 初期开发中