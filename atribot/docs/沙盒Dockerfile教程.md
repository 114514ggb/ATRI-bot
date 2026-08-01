# 🐳 沙盒 Dockerfile 教程

ATRI 默认的 AI 代码沙盒基于 **Docker**，镜像构建文件位于：

```
atribot/LLMchat/sandbox/Dockerfile
```

本文档说明这个 Dockerfile 是干什么的、如何构建、如何自定义，以及它在项目里是怎么被用起来的。

---

## 1. 这个镜像的作用

当 LLM 调用 `run_python_code` / `run_command` 工具时，代码并不是在机器人本机执行的，而是被发送到一个**独立的 Docker 容器**里运行，从而与主程序隔离，避免危险代码破坏环境。

这个 Dockerfile 就是用来构建「沙盒镜像」的，里面预装了：

- **系统级**：`ffmpeg`（音视频处理）、`tmux`、`curl`、`wget`、中文字体 `fonts-wqy-zenhei`（防止 matplotlib 中文乱码）、OpenCV 运行库
- **Python 包**：`numpy`、`pandas`、`matplotlib`、`seaborn`、`pillow`、`opencv-python-headless`、`requests`、`scipy`、`sympy`

> 沙盒实际执行逻辑在 `atribot/LLMchat/sandbox/docker_sandbox.py`（`DockerSandbox` 类）。

---

## 2. 逐段解读 Dockerfile

```dockerfile
FROM python:3.12-slim
```

基础镜像使用轻量的 Python 3.12 精简版，体积小、启动快。

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
```

环境变量：
- `PYTHONDONTWRITEBYTECODE=1`：不生成 `__pycache__`，减少磁盘占用
- `PYTHONUNBUFFERED=1`：输出实时刷新，方便看日志
- `MPLBACKEND=Agg`：matplotlib 使用无界面后端，避免在容器里报 `display` 相关错误
- `LANG/LC_ALL=C.UTF-8`：保证中文等 UTF-8 文本正常显示

```dockerfile
RUN apt-get update && apt-get install -y --fix-missing --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    fonts-wqy-zenhei \
    tmux \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*
```

安装系统依赖：
- `ffmpeg`：音视频处理（沙盒里常用它转码/剪辑）
- `libglib2.0-0 / libsm6 / libxext6 / libxrender-dev`：OpenCV 运行时所需的图形库
- `fonts-wqy-zenhei`：文泉驿正黑中文字体，**matplotlib 画图含中文时必备**
- `tmux / curl / wget`：终端复用与网络工具
- 结尾 `rm -rf /var/lib/apt/lists/*` 清理 apt 缓存，减小镜像体积

```dockerfile
WORKDIR /workspace
```

容器内工作目录为 `/workspace`，与 `docker_sandbox.py` 中的 `work_dir = "/workspace"` 保持一致。

```dockerfile
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    pillow \
    opencv-python-headless \
    requests \
    scipy \
    sympy
```

安装常用 Python 科学计算 / 数据处理包。`--no-cache-dir` 同样是为了减小镜像体积。

> `opencv-python-headless` 使用无 GUI 版本，适合容器环境。

```dockerfile
VOLUME ["/workspace/groups"]
```

把 `/workspace/groups` 声明为数据卷，方便跨容器共享文件（如沙盒间传递文件）。

```dockerfile
CMD ["tail", "-f", "/dev/null"]
```

容器启动后保持空转（`tail -f /dev/null`），这样容器能一直存活，沙盒工具随时往里面发命令执行。`docker_sandbox.py` 启动容器时也传了 `command="tail -f /dev/null"`。

---

## 3. 构建镜像

在**项目根目录**执行：

```bash
docker build -t atri-sandbox:latest -f atribot/LLMchat/sandbox/Dockerfile .
```

> 镜像名 `atri-sandbox:latest` 要和配置里的 `image` 字段一致（见第 4 节），否则沙盒会退回去拉取默认的 `python:3.12-slim`。

首次构建需要下载基础镜像和安装包，可能要几分钟；之后改动 Dockerfile 重新构建会利用缓存，速度很快。

---

## 4. 项目里如何配置使用

镜像名配置在 `assets/config.json`：

```json
"sand_box": {
    "image": "atri-sandbox:latest"
}
```

启动时 `bot_framework.py` 会读取该配置创建沙盒：

```python
sand_box: SandBoxBase = DockerSandbox(config=self.config.sand_box)
await sand_box.start()
container.register("SandBox", sand_box, cleanup=sand_box.stop)
```

注意：
- 沙盒是**可选**的，初始化失败不会阻断 Bot 启动（`_start_sandbox()` 失败只记 warning）
- 使用前建议先 `container.exists("SandBox")` 检查是否启动成功
- `DockerSandbox` 还支持其他参数（内存限制、CPU 配额、进程数限制、网络模式等），详见 `assets/如何配置配置文件.py` 与 `docker_sandbox.py` 的 `__init__` 注释

---

## 5. 自定义扩展

### 5.1 加 Python 包

在 `pip install` 那一段加上包名即可，例如：

```dockerfile
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    ...
    jieba \
    beautifulsoup4
```

### 5.2 加系统软件

在 `apt-get install` 的列表里追加，例如：

```dockerfile
RUN apt-get update && apt-get install -y --fix-missing --no-install-recommends \
    ffmpeg \
    ...
    git \
    vim
```

### 5.3 换基础镜像 / 换 Python 版本

想用更高版本 Python（比如 3.14），把第一行改成：

```dockerfile
FROM python:3.14-slim
```

> ⚠️ 更换基础镜像或 Python 版本后，之前沙盒里缓存的依赖都会被重建；若项目其他部分依赖特定 Python 版本，注意保持一致。

### 5.4 自定义后如何生效

1. 修改 `Dockerfile`
2. 重新构建：`docker build -t atri-sandbox:latest -f atribot/LLMchat/sandbox/Dockerfile .`
3. 重启 Bot（或调用沙盒的 `restart()`，它会删除旧容器并用新镜像重建）

---

## 6. 常见问题

| 问题 | 原因 / 解决 |
|---|---|
| 沙盒启动报 `Failed to start Docker sandbox` | 本机 Docker 未启动，或 `config.json` 里 `sand_box.image` 与本地镜像名不一致 |
| matplotlib 中文显示为方块 | 镜像里没装中文字体（`fonts-wqy-zenhei`），或没设 `MPLBACKEND=Agg` |
| OpenCV 导入报错 | 缺少图形库，确认已装 `libglib2.0-0 / libsm6 / libxext6 / libxrender-dev` |
| 改完 Dockerfile 后不生效 | 没重新 build，或 build 出来的 tag 和配置里 `image` 不一致 |
| 容器一直不退出、占用资源 | 沙盒是常驻容器（`tail -f /dev/null`），由 Bot shutdown 时统一清理；异常退出时可用 `docker ps -a` 手动清理带 `atri.sandbox.managed=true` 标签的容器 |

---

## 7. 验证镜像是否可用

构建完成后，可手动进入容器测试：

```bash
docker run --rm -it atri-sandbox:latest bash
```

然后在容器里验证：

```bash
python -c "import numpy, pandas, matplotlib, cv2; print('ok')"
python -c "import matplotlib.pyplot as plt; plt.rcParams['font.sans-serif']=['WenQuanYi Zen Hei']; print('字体ok')"
ffmpeg -version | head -1
```
