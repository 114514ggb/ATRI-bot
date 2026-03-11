FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ATRI_SOURCE_CONFIG_PATH=/app/assets/config.json \
    ATRI_RUNTIME_CONFIG_PATH=/tmp/atri-config.runtime.json \
    ATRI_CONFIG_PATH=/tmp/atri-config.runtime.json

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-linux.txt ./requirements-linux.txt

RUN pip install --upgrade pip \
    && pip install -r requirements-linux.txt

COPY . .

RUN chmod +x /app/docker/python/docker-entrypoint.sh

ENTRYPOINT ["/app/docker/python/docker-entrypoint.sh"]