from fastapi import APIRouter

from app.api.endpoints import auth, classes, tasks, guacamole

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(classes.router, prefix="/classes", tags=["classes"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(guacamole.router, prefix="/guacamole", tags=["guacamole"])