"""FastAPI 应用装配。

和同服务器的 xiangq 保持同一套分工：本服务**只提供接口**，
页面由宿主机 Nginx 直接读 ``sites/moxi``，不经过 Python。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.game.store import GameError

app = FastAPI(
    title=settings.name,
    version=settings.version,
    description="MoXi API。两个人各写一个词，撞上就赢。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(GameError)
async def game_error_handler(request: Request, exc: GameError) -> JSONResponse:
    """业务错误统一成 {detail}，前端直接拿去 toast。"""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    # 对局状态必须实时，别让浏览器或中间层缓存住。
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.name,
        "version": settings.version,
        "message": "API only —— 前端页面由 Nginx 提供。",
        "docs": "/docs",
        "health": "/api/health",
    }
