# 不使用 `# syntax=docker/dockerfile:1`：构建不需要额外 frontend，
# 显式声明会让 BuildKit 额外拉取 docker/dockerfile 镜像（离线/镜像源异常时直接构建失败）。
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Debian 源默认走官方地址；国内网络可传 --build-arg APT_MIRROR=mirrors.ustc.edu.cn 换成镜像站
ARG APT_MIRROR=deb.debian.org
RUN grep -rl 'deb.debian.org' /etc/apt > /tmp/apt-mirror-targets 2>/dev/null || true; \
    if [ -s /tmp/apt-mirror-targets ]; then \
        xargs -r sed -i "s|deb.debian.org|${APT_MIRROR}|g" < /tmp/apt-mirror-targets; \
    fi; \
    rm -f /tmp/apt-mirror-targets

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-linux.txt ./requirements-linux.txt

# PyPI 默认官方源；国内可传 --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --upgrade pip --index-url "${PIP_INDEX_URL}" \
    && pip install --index-url "${PIP_INDEX_URL}" uv \
    && uv pip install --system --index-url "${PIP_INDEX_URL}" -r requirements-linux.txt

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
ARG APT_MIRROR=deb.debian.org
RUN grep -rl 'deb.debian.org' /etc/apt > /tmp/apt-mirror-targets 2>/dev/null || true; \
    if [ -s /tmp/apt-mirror-targets ]; then \
        xargs -r sed -i "s|deb.debian.org|${APT_MIRROR}|g" < /tmp/apt-mirror-targets; \
    fi; \
    rm -f /tmp/apt-mirror-targets; \
    if [ "$WITH_NODE" = "1" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends nodejs npm \
        && rm -rf /var/lib/apt/lists/* /root/.npm; \
    fi

WORKDIR /app

COPY . .

RUN chmod +x /app/docker/python/docker-entrypoint.sh

CMD ["python", "/app/main.py"]

ENTRYPOINT ["/app/docker/python/docker-entrypoint.sh"]