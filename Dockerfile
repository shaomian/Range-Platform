# syntax=docker/dockerfile:1

# ---------- Stage 1: build the Vue frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Docker CLI + compose plugin source ----------
FROM docker:27-cli AS dockercli

# ---------- Stage 2: python runtime ----------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Docker CLI + compose plugin so the backend can drive the host daemon (DooD)
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-compose \
    /usr/local/libexec/docker/cli-plugins/docker-compose

# Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Backend application code
COPY backend/app ./app

# Compiled frontend served by FastAPI
COPY --from=frontend /build/dist ./static

# Persistent database location (mounted as a volume in compose)
RUN mkdir -p /data

ENV STATIC_DIR=/app/static \
    DATABASE_URL=sqlite:////data/vulhub_hub.db \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
