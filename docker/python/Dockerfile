# syntax=docker/dockerfile:1

FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-linux.txt ./requirements-linux.txt

RUN pip install --upgrade pip \
    && pip install uv \
    && uv pip install --system -r requirements-linux.txt

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ATRI_SOURCE_CONFIG_PATH=/app/assets/config.json \
    ATRI_RUNTIME_CONFIG_PATH=/tmp/atri-config.runtime.json \
    ATRI_CONFIG_PATH=/tmp/atri-config.runtime.json

COPY --from=builder /usr/local /usr/local

# npx 型 MCP 服务需要 Node.js；不需要时可用 --build-arg WITH_NODE=0 省下约 300MB
ARG WITH_NODE=1
RUN if [ "$WITH_NODE" = "1" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends nodejs npm \
        && rm -rf /var/lib/apt/lists/* /root/.npm; \
    fi

WORKDIR /app

COPY . .

RUN chmod +x /app/docker/python/docker-entrypoint.sh

ENTRYPOINT ["/app/docker/python/docker-entrypoint.sh"]