# db/Dockerfile
#
# PostgreSQL 18 + pgroonga + pgvector。
# - pgroonga 用 Groonga 官方镜像（底层就是 postgres:18 官方镜像，扩展已装好），
#   不再从 packages.groonga.org 拉包，避免该源在国内极慢/超时。
#   `latest-debian-18` 跟随 PG18 的 PGroonga 最新版（当前 4.1.0）。
# - pgvector 用 PGDG 仓库的预编译包（基础镜像已配置 apt.postgresql.org 源），不再源码编译。

FROM groonga/pgroonga:latest-debian-18

# Debian 源默认走官方地址；国内网络可传 --build-arg APT_MIRROR=mirrors.ustc.edu.cn 换成镜像站
ARG APT_MIRROR=deb.debian.org
RUN grep -rl 'deb.debian.org' /etc/apt > /tmp/apt-mirror-targets 2>/dev/null || true; \
    if [ -s /tmp/apt-mirror-targets ]; then \
        xargs -r sed -i "s|deb.debian.org|${APT_MIRROR}|g" < /tmp/apt-mirror-targets; \
    fi; \
    rm -f /tmp/apt-mirror-targets

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-18-pgvector \
    && rm -rf /var/lib/apt/lists/*

