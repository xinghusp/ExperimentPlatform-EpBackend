import uvicorn
import os

from celery.bin.graph import workers
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from six import iteritems
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time

from app.api.api import api_router
from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 创建上传文件目录
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)

app = FastAPI(
    title="实验环境管理平台API",
    description="实验环境管理平台后端API",
    version="1.0.0",
)

# 请求处理时间中间件
class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

# 设置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加性能跟踪中间件
# app.add_middleware(ProcessTimeMiddleware)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "欢迎使用实验环境管理平台API"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请联系管理员"}
    )
logging.basicConfig(
    level=logging.WARNING,  # 设置日志输出等级为DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def start_worker():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
if __name__ == "__main__":
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True,workers=32,
    #     limit_concurrency=128,       # 限制每个worker的最大并发连接数
    #     timeout_keep_alive=120,      # 增加保活超时
    #     access_log=False)            # 减少日志开销)
    # 本地开发时使用此代码
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--multiprocess":
        # 手动启动多进程模式 (本地测试多进程)
        import multiprocessing

        worker_count = min(8, multiprocessing.cpu_count() * 2 + 1)
        print(f"启动 {worker_count} 个工作进程...")
        # 多进程启动代码...
        import multiprocessing
        import uvicorn

        worker_count = min(8, multiprocessing.cpu_count() * 2 + 1)
        print(f"启动 {worker_count} 个工作进程...")

        processes = []
        for _ in range(worker_count):
            p = multiprocessing.Process(target=start_worker)
            p.start()
            processes.append(p)

        for p in processes:
            p.join()



    else:
        # 单进程开发模式
        print("以开发模式启动 (单进程，自动重载)...")
        import uvicorn

        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)