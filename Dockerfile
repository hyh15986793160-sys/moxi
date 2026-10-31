# 只构建 API 镜像。
# 前端是纯静态产物，由宿主机 Nginx 直接读 sites/moxi，不进镜像、不经过 Python。
FROM python:3.12-slim AS runtime

# 国内机器直连 pypi.org 很慢，默认走腾讯云内网镜像。
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser
WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

# 房间状态在进程内存里，只能单 worker，多 worker 会把两个人分到不同的进程。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
