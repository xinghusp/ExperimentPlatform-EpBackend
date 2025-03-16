from fastapi import APIRouter

from app.api.endpoints import (
    auth, classes, tasks, student_tasks, environment,
    ecs, guacamole, jupyter, admin, nginx_auth
)

api_router = APIRouter()

# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# 管理员路由
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(classes.router, prefix="/classes", tags=["classes"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

# 学生路由
api_router.include_router(student_tasks.router, prefix="/student", tags=["student"])

# 环境管理路由
api_router.include_router(environment.router, prefix="/environments", tags=["environments"])

# 实验环境路由
api_router.include_router(ecs.router, prefix="/ecs", tags=["ecs"])
api_router.include_router(guacamole.router, prefix="/guacamole", tags=["guacamole"])
api_router.include_router(jupyter.router, prefix="/jupyter", tags=["jupyter"])

api_router.include_router(nginx_auth.router, prefix="/nginx_auth", tags=["nginx_auth"])