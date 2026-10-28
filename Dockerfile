# One container runs the API and the Operation worker together: both read and write
# the rendered documents under artifacts/, so they share one disk. See render.yaml.

FROM node:22-slim AS frontend
WORKDIR /app
COPY openapi/types.ts openapi/types.ts
COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm ci --prefix frontend
COPY frontend/ frontend/
RUN npm run build --prefix frontend

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app

# Fonts the CV templates name: Liberation stands in for Arial/Helvetica/Times,
# Noto Sans Hebrew covers the RTL template.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-liberation fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
# The s3 extra: a deployed instance keeps its immutable payloads in a bucket.
RUN uv sync --frozen --no-dev --extra s3 --no-install-project
RUN playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*

COPY . .
RUN uv sync --frozen --no-dev --extra s3
COPY --from=frontend /app/frontend/dist frontend/dist

CMD ["scripts/serve.sh"]
