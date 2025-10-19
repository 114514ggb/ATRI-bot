Rsync '.\DNA.wav' atri@172.29.0.2:~/py_project/ATRI-main/document/audio/sing

/mnt/e/程序文件/python/ATRI-main

rsync -avz --progress --delete ./document/ atri@172.29.0.2:~/py_project/ATRI-main/document
rsync -avz --progress ./atribot/ atri@172.29.0.2:~/py_project/ATRI-main/atribot

tmux kill-session -t atribot

ffmpeg -i input.mp4 -c:v libx264 -b:v 2000k -c:a copy output.mp4