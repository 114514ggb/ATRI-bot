#!/bin/sh
set -e

python /app/docker/python/prepare_config.py

# 允许 `docker run <image> <cmd>` / compose 的 command 覆盖默认启动命令
exec "$@"