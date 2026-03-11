#!/bin/sh
set -e

python /app/docker/python/prepare_config.py

exec python /app/main.py