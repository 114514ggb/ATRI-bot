# db/Dockerfile

FROM postgres:18-bookworm AS pgvector-builder

ARG PGVECTOR_VERSION=v0.8.6

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    gcc \
    postgresql-server-dev-18 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch ${PGVECTOR_VERSION} https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make \
    && make install DESTDIR=/pgvector-artifacts

FROM postgres:18-bookworm

RUN apt-get update && apt-get install -y --fix-missing \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN install -d /usr/share/postgresql-common/pgdg && \
    curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc

RUN . /etc/os-release && \
    sh -c "echo 'deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main' > /etc/apt/sources.list.d/pgdg.list"

RUN . /etc/os-release && \
    curl -fsSL https://packages.groonga.org/debian/groonga-archive-keyring.gpg \
    | gpg --dearmor -o /usr/share/keyrings/groonga-archive-keyring.gpg && \
    sh -c "echo 'deb [signed-by=/usr/share/keyrings/groonga-archive-keyring.gpg] https://packages.groonga.org/debian/ ${VERSION_CODENAME} main' > /etc/apt/sources.list.d/groonga.list"

RUN apt-get update && apt-get install -y --fix-missing \
    postgresql-18-pgdg-pgroonga \
    && apt-get purge -y curl ca-certificates gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 拷贝编译好的 pgvector（vector.so + control + SQL 脚本），自动落到 PG18 的 lib/extension 目录
COPY --from=pgvector-builder /pgvector-artifacts/ /