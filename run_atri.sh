#!/bin/bash

cd /home/atri/py_project/ATRI-main
source /home/atri/py_project/ATRI-main/.venv/bin/activate

#LOG_FILE="/home/atri/py_project/ATRI-main/atribot_$(date +%Y%m%d_%H%M%S).log"

if command -v tmux >/dev/null 2>&1; then

    #tmux new-session -d -s atribot "python3 main.py > '$LOG_FILE' 2>&1"
    tmux new-session -d -s atribot "python3 main.py"
    echo "已用 tmux 启动，会话名为 atribot"
    #echo "日志保存到: $LOG_FILE"
else
    nohup python3 main.py > /dev/null 2>&1 &
    echo "未检测到 tmux，已用 nohup 启动"
fi