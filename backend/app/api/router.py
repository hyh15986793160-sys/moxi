"""API 总机：把各业务模块的 router 挂到 /api 下。"""

from fastapi import APIRouter

from app.api import health, rooms

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(rooms.router)
