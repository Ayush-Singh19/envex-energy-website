# syntax=docker/dockerfile:1

# ---- build: resolve dependencies into /app/.venv with uv ----
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# ---- runtime: slim image, non-root user ----
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 envex
WORKDIR /app
COPY --from=builder --chown=envex:envex /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000
USER envex
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/v1/health', timeout=4)"

# Apply migrations, then serve. Proxy headers are handled in app.core.client_ip
# (set TRUSTED_PROXY_HOPS=1 behind Render/Railway), not by uvicorn, which would trust
# client-supplied X-Forwarded-For values when told to trust every proxy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-proxy-headers"]
