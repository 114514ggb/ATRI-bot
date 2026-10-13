# Windows 部署指南

本文档面向**在 Windows 上部署 ATRI-bot** 的场景，重点说明三条可选路径的取舍、
原生 Windows 的完整步骤，以及最容易踩的坑。

> 结论先行：**推荐直接用 Docker Compose（路径 A）**。原生 Windows（路径 C）完全可行，
> 但需要手工安装两个 PostgreSQL 服务端扩展（`pgvector` + `pgroonga`），这是最耗时的一步。

---

## 0. 硬性要求

| 项目 | 要求 | 说明 |
|---|---|---|
| Python | **3.14**（`>=3.14`） | `pyproject.toml` 的 `requires-python`。用 3.13 会**直接被 `uv sync` / `pip install .` 拒绝**，强制安装（`--ignore-requires-python`）后可能在退出时触发 `asyncio` 行为差异告警 |
| PostgreSQL | 16 / 17 / 18 | 项目仅支持 PostgreSQL |
| pgvector | 必装 | 向量检索（`HNSW`，1024 维） |
| pgroonga | 必装 | 全文检索（混合召回的另一路） |
| NapCat | 最新版 | 提供 QQ 协议端 |

> 注意：`pgvector` 与 `pgroonga` 都是 **PostgreSQL 服务端扩展**，不是 pip 包，
> 不能用 `pip install` 安装。缺失 `pgroonga` 时 bot 仍可启动（记忆检索会降级为纯向量），
> 但**建库脚本会在这两行中断**，导致后续建表全部不执行。

---

## 1. 选择部署路径

| 路径 | 适用 | 优点 | 代价 |
|---|---|---|---|
| **A. Docker Compose** | 推荐，绝大多数人 | 一条命令起 DB（含两个扩展）与 bot，无扩展安装烦恼 | 需要 Docker Desktop |
| **B. WSL2** | 想在 Linux 环境下跑 bot、把 Windows 当宿主 | 可用 apt 装扩展，环境与 CI 一致 | 与 Windows 侧存在文件系统边界，需配 `path_mapping` |
| **C. 原生 Windows** | 不想装 Docker / WSL | 无虚拟化开销，调试直接 | **需要手工编译 pgvector、解压 pgroonga**；沙盒需 Docker 或改用 `none` 后端 |

三条路径可以混用：例如 **数据库用 Docker（路径 A 的 `db` 容器），bot 跑在原生 Windows**——
这是最省事的组合，见 §3。

---

## 2. 路径 A：Docker Compose（推荐）

```powershell
# 1. 复制环境变量模板
Copy-Item .env.docker.example .env

# 2. 编辑 .env：至少设置 ATRI_PANEL_TOKEN（面板登录口令），并核对端口与 NapCat 一致

# 3. 构建并启动（数据库容器会自动装好 pgvector + pgroonga）
docker compose up -d --build
```

面板地址 `http://localhost:5308/admin/`。

### docker.sock 说明

`docker-compose.yml` 挂载了 `/var/run/docker.sock`，用于容器内的 AI 沙盒拉起兄弟容器。
在 **Docker Desktop for Windows** 下这条挂载不成立（Windows 用的是 named pipe
`npipe:////./pipe/docker_engine`）。影响范围仅限 **Docker 沙盒后端**，不影响 bot 主功能。

处理方式二选一：

1. 保持沙盒镜像已构建、接受沙盒不可用；或
2. 让沙盒改用本机直执行：把 `assets/config.json` 的 `sand_box.type` 改成 `"none"`。

---

## 3. 组合方案：数据库用 Docker，bot 跑原生 Windows

这是最推荐的"原生 Windows"玩法——绕开扩展安装，同时保留原生调试体验。

```powershell
# 只起数据库容器（注意：默认端口映射只绑 127.0.0.1，本机访问无需改动）
docker compose up -d db

# 然后在项目根目录用 uv 起 bot
uv sync
uv run main.py
```

`assets/config.json` 的数据库配置保持默认即可（宿主机 `127.0.0.1:5432`）：

```json
"database": {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "atri",
    "password": "180710",
    "database": "atri"
}
```

> 容器初始化时创建的应用用户/库名由 `.env` 的 `ATRI_DB_APP_USER` / `ATRI_DB_NAME` 决定，
> 默认 `atri` / `atri`，与上面一致。

---

## 4. 路径 C：原生 Windows 完整步骤

### 4.1 安装 Python 3.14 与依赖

推荐 [uv](https://docs.astral.sh/uv/)（会自动按 `.python-version` 拉取 3.14）：

```powershell
uv sync
```

若要用 pip，务必先确认解释器版本：

```powershell
python -c "import sys; print(sys.version)"   # 必须显示 3.14.x
pip install -r requirements-windows.txt
```

> `requirements-windows.txt` 与 `requirements-linux.txt` 的差别只有
> `colorama` / `pywin32` / `tzdata` 三个平台专属包。

### 4.2 安装 PostgreSQL 与两个扩展

1. 用官方 installer 安装 PostgreSQL 16/17/18，安装目录例如
   `C:\Program Files\PostgreSQL\18`。

2. **pgvector**（需编译）：

   ```powershell
   git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
   cd pgvector
   # 需要 "x64 Native Tools Command Prompt for VS 2022"（含 MSVC + nmake）
   set "PGROOT=C:\Program Files\PostgreSQL\18"
   nmake /F Makefile.win
   nmake /F Makefile.win install
   ```

   参考：<https://github.com/pgvector/pgvector#windows>

3. **pgroonga**（官方提供 Windows zip）：

   到 <https://pgroonga.github.io/install/windows.html> 下载与你的 PostgreSQL
   主版本对应的 zip（如 `pgroonga-4.1.0-postgresql-18-x64.zip`），**解压到
   PostgreSQL 安装目录**（`C:\Program Files\PostgreSQL\18`），合并覆盖同名文件夹。

4. 建库并启用扩展：

   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres
   ```

   ```sql
   CREATE DATABASE atri;
   \c atri
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pgroonga;
   ```

   然后执行项目自带的建表脚本（`docker/db/info.sql`，或用 `\i` 指定绝对路径）：

   ```sql
   \i 'E:/程序文件/python/ATRI-main/docker/db/info.sql'
   ```

   > `docker/db/init/01-init.sh` 是给容器用的 shell 脚本；原生 Windows 请用
   > `docker/db/info.sql`，内容一致。

   验证：

   ```sql
   SELECT extname FROM pg_extension;   -- 应包含 vector 与 pgroonga
   ```

### 4.3 ffmpeg（可选，但强烈建议）

音频/视频转码依赖 ffmpeg。Windows 默认**不预装**，缺失时转码会静默失败（日志会给出一次
warning）。下载 <https://www.gyan.dev/ffmpeg/builds/> 的 release 包，解压后把 `bin`
目录加入系统 `PATH`，重开终端验证：

```powershell
ffmpeg -version
```

### 4.4 沙盒后端选择

| 想要 | 配置 |
|---|---|
| 完整隔离的代码沙盒 | 保持 `"type": "docker"`，确保 **Docker Desktop 已启动**，并预先构建镜像：`docker build -t atri-sandbox:latest -f atribot/LLMchat/sandbox/Dockerfile .` |
| 本机直执行（无隔离，最省事） | 改成 `"type": "none"`，工作区默认落在 `document/work`；Windows 上优先使用 Git Bash，找不到则退回 `cmd` |
| 云端沙盒 | `"type": "e2b"`，需 `pip install e2b-code-interpreter` 并提供 `api_key` |

```json
"sand_box": {
    "type": "none",
    "work_dir": "E:/程序文件/python/ATRI-main/document/work"
}
```

> 沙盒为**可选**能力：初始化失败只会记录一条异常日志，不会阻断 bot 启动，
> 但 4 个沙盒工具（`run_python_code` / `run_command` / `send_file` / `add_file`）
> 对模型不可见。

### 4.5 路径映射（Bot 与 NapCat 不在同一文件系统时）

如果 NapCat 跑在 Windows 而 bot 跑在 WSL（或 Docker），bot 发出的 `file://` 路径
对 NapCat 不可读，需要在 `assets/config.json` 配置前缀映射：

```json
"file_path": {
    "path_mapping": {
        "E:/程序文件/python/ATRI-main": "/mnt/e/程序文件/python/ATRI-main"
    }
}
```

匹配不区分大小写、支持多条（最长前缀优先）。典型症状：TTS 语音、表情包、
本地图片/文件发送失败（NapCat 报"文件不存在"）。

### 4.6 TTS（可选）

参考音频路径已不再硬编码。可在 `assets/config.json` 配置：

```json
"tts": {
    "api_url": "http://127.0.0.1:9880",
    "emotions": {
        "平静": {
            "refer_wav_path": "D:/tts_reference/ref.mp3",
            "prompt_text": "参考文本",
            "prompt_language": "ja"
        }
    }
}
```

不配置时回退内置三情感（`高兴` / `机械` / `平静`），参考音频从
`document/audio/tts_reference/` 读取；文件缺失时只记录 warning。

### 4.7 启动

```powershell
uv run main.py
```

> ⚠️ 必须在**项目根目录**执行，路径解析依赖工作目录。

---

## 5. 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `uv sync` 报 `requires-python` 不满足 | 当前解释器不是 3.14 | `uv python install 3.14` 后重试；不要加 `--ignore-requires-python` |
| 建库脚本中途停止、后续表都没建 | 缺 `pgvector` / `pgroonga` | 按 §4.2 安装扩展后重新执行 `docker/db/info.sql` |
| 日志反复出现 `hybrid_recall 混合查询失败,降级到纯向量` | 数据库缺 `pgroonga` | 装上 pgroonga 后重启；短期可忽略（检索仍可用，只是少了全文一路） |
| 日志出现 `未检测到 ffmpeg...` | PATH 中无 ffmpeg | 按 §4.3 安装，或接受音视频转码降级 |
| `无法连接 Docker daemon，AI 沙盒不可用` + Windows 提示 | Docker Desktop 未启动 / 只装在 WSL | 启动 Docker Desktop，或把 `sand_box.type` 改为 `"none"` |
| 启动时直接退出，提示 `e2b_code_interpreter 模块未安装` | `sand_box.type` 是 `e2b` 但未安装依赖 | `pip install e2b-code-interpreter`，或改 `sand_box.type` |
| TTS 报文件不存在 / 日志 `TTS 参考音频不存在` | 参考音频路径未配置或对 TTS 侧不可见 | 按 §4.6 配置绝对路径 |
| 图片/语音发不出去，NapCat 报文件不存在 | 缺少 `path_mapping` | 按 §4.5 配置 |
| 面板打不开 | 端口被占用或未绑对地址 | 检查 `config.web_panel`（默认 `127.0.0.1:5125`）；面板启动失败**不影响** bot 主服务 |
| 控制台出现乱码色块 | 旧版 conhost 不支持 ANSI | 改用 Windows Terminal，或设置 `ATRI_FILE_LOG=0` 只看文件日志 |

---

## 6. 与 Linux / Docker 的差异速查

| 能力 | 原生 Windows | Linux / Docker |
|---|---|---|
| 数据库扩展安装 | 手工（pgvector 需 MSVC，pgroonga 解压 zip） | apt / 容器内已预装 |
| Docker 沙盒 | 需 Docker Desktop（named pipe） | 直接可用 |
| 本机沙盒（`type: none`） | 支持（Git Bash 优先，否则 cmd） | 支持（`/bin/sh`） |
| Web 面板终端（沙盒终端） | 支持 cmd/bash/sh；PowerShell 下不开放 | 支持 |
| 优雅关闭 | Ctrl+C 或面板"停止" | SIGINT / `docker compose stop` |
| 日志轮转 | 已针对 Windows 文件锁做退避重试 | 标准实现 |

---

## 7. 相关文档

- 主文档：仓库根目录 `README.md`（快速开始、配置项说明）
- 沙盒镜像自定义：`atribot/docs/沙盒Dockerfile教程.md`
- 数据库表结构改动：`atribot/docs/db_migrations.md`
- 配置项逐条说明：`assets/如何配置配置文件.md` / `.py`