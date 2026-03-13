<img src=".\assets\ATRI-bot.png" width = "400" height = "400" alt="ATRI-bot" align=right />
<div align="center">

<p align="right">
  <a href="./README.md">
    <img src="https://img.shields.io/badge/lang-简体中文-red" alt="简体中文">
  </a>
  <a href="./README.en.md">
    <img src="https://img.shields.io/badge/lang-English-blue" alt="English">
  </a>
</p>

# ATRI-bot

>_时间流逝吧，你是多么的残酷；时间停止吧，你是多么的美丽_
>
> — *𝓐𝓣𝓡𝓘 -𝓜𝔂 𝓓𝓮𝓪𝓻 𝓜𝓸𝓶𝓮𝓷𝓽𝓼-*
>
项目Logo由[吖密](https://space.bilibili.com/1196260828)绘制  
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED.svg)](https://www.docker.com/)
[![NapCat](https://img.shields.io/badge/Backend-NapCat-green.svg)](https://github.com/NapNeko/NapCatQQ)

</div>

## 📖 前言

来自萌新到处学习(抄袭，不对是集百家之长✨)做出来私用的神秘项目.
主要是**按照自己的需求**编写一个专到狭窄的学习性质的项目(专注于提供一个深度定制化的群聊机器人体验),发出来是用来交流学习的.
希望这个 Bot 能像亚托莉一样成为你珍贵的伙伴(虽然现在还不是很完善)

---

## ✨ 项目核心功能

简单来说，这是一个基于 **NapCat** 对接、专注于群聊场景的 QQ Bot。目前主要能力也基本都围绕群聊展开。

### 🧠 深度 LLM 聊天集成
完全自主实现的 LLM 聊天全流程，从输入处理到输出响应完全可控：
- **全异步高并发**：回复流程完全异步，支持 Key 号池轮询，面对多个群聊的高并发场景也能轻松应对。
- **自主可控**：支持函数调用（Function Calling）及 **MCP (Model Context Protocol)** 还有 **skills** 配置(虽然对skills支持不全)。
- **RAG 记忆系统**：基于 RAG（检索增强生成）实现的记忆功能，支持知识库问答，让 Bot 拥有“长期记忆”。
- **高可用设计**：设计了备用 API 响应机制。当主模型响应错误时，会自动降级到配置的其他模型（虽然速度可能稍慢，但保证有问必达）。
- **拟人化交互**：
  - 支持自然地发送表情包。
  - 模拟人类说话习惯，支持分段发送消息。
  - **主动话题参与**：达到一定条件时，会尝试主动回复群消息，融入话题。
  - **用户画像维护**：维护 User 文档用于嵌入上下文，保证对同一用户的态度一致性。
  - 支持人设切换等基础功能。

### 💻 类 Unix 命令系统
内置一套类 Unix 风格的命令系统，在群里 `@bot` 后以 `/` 开头即可触发（例如 `@atri-bot /help --list`，这里必须使用 QQ 的真实 `@` 提及，而不是直接输入名字文本）：
- **参数解析**：支持 `-` 和 `--` 等参数风格，内置参数类型验证。
- **权限管理**：内置权限系统，支持拉黑或授予管理员权限。可在任意处理环节校验 User 权限，拒绝非法执行。
- **自动帮助文档**：只要在代码中使用装饰器并添加参数说明，即可自动生成详细的 `--help` 提示。

### 🛠️ 其他实用功能
- **高性能关键词匹配**：配置文件支持关键词响应，底层采用 **AC 自动机** 算法，即使配置上万条匹配项也能保持毫秒级响应
- **群成员变动提醒**：有人加入或退出群聊时自动通知
- **戳一戳互动**：被戳时会有反应，甚至会“戳回去”
- **强健的架构**：数据库采用连接池，消息接收引入消息队列机制，抗压能力 Max

---

## 🚀 快速开始 (How to Run)

### 1. 前端连接 (NapCat)
首先需要一个能够与 QQ 通信的前端，推荐使用 NapCat：
[NapCat 安装指南](https://napneko.github.io/guide/napcat)
[NapCat 项目地址](https://github.com/NapNeko/NapCatQQ)
> *注：你也可以自己实现前端，只要能对接上即可。*

### 2. 数据库配置 (PostgreSQL)
项目当前仅支持 PostgreSQL 数据库。
1.  **安装数据库**：建议安装较新的 PostgreSQL 版本。[官方安装文档](https://www.postgresql.org/download/)
2.  **安装向量插件**：必须安装 `pgvector` 插件以支持 RAG 功能。[pgvector 项目地址](https://github.com/pgvector/pgvector)
3.  **数据库初始化**：
    项目提供了初始化 SQL 文件：`docker\db\info.sql`。
    进入数据库（Linux 示例）：
    ```bash
    sudo -u postgres psql
    ```
    然后按顺序执行 `info.sql` 中的内容创建表结构。


### 3. 模型与环境配置
#### 🤖 嵌入模型 (Embedding)
推荐优先使用本地的 `Qwen3-Embedding-0.6B:F16`。当然你也可以接入其他 Embedding API，只是仓库里目前主要按 Ollama 的使用方式测试过。
推荐使用 [Ollama](https://ollama.com/) 进行本地部署：
```bash
ollama run Qwen3-Embedding-0.6B:F16
```

> **注意**：如果更换 Embedding 模型，之前构建的向量数据需要重新构建。


#### 🗣️ 语音合成 (TTS) - 可选
支持接入 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)。
实现 Bot 主动发送语音或通过命令调用语音功能，可以设置语速、情感等常用参数；当然前提是你已经准备好了自己的语音模型。  
使用前需要修改 `atribot\commands\audio\TTS.py` 中的参考音频路径，以及 GPT-SoVITS 接口端口地址。  
```json
{
    "这里是对应的情感": {
        "refer_wav_path": "这里是参考音频的完整路径",
        "prompt_text": "参考音频的对应文本",
        "prompt_language": "参考文本对应的语言"
    },           
    "平静": {
        "refer_wav_path": "/home/atri/tts_reference/夏生さんが望むのでしたら.mp3",
        "prompt_text": "夏生さんが望むのでしたら",
        "prompt_language": "ja"
    }
}
```


#### 📦 沙盒环境 (sandbox) - 可选

为 AI 模型配备了默认的**代码沙盒环境**，使其能够安全地执行用户请求或自主生成的代码片段。当前实现基于 **Docker** 🐳沙盒，支持运行 Python 等语言的代码，可用于代码解释、数据计算等场景。

- **扩展性**：如需支持其他类型的沙盒（如 Web 沙盒、系统命令沙盒），可继承 `atribot\LLMchat\sandbox\sandbox_base.py` 中的基类并实现相应接口。
- **文件操作**：支持了在ai上下文中看见的文件可以放到python环境中对文件进行简单处理


#### ⚙️ 配置文件
在启动前，请务必检查 `assets` 目录中的配置：
1.  参考 `assets\如何配置配置文件.py` 了解配置详情。
2.  配置 `supplier_config.json` (模型供应商配置)。
3.  配置 `config.json` (项目基础配置)。
4.  **MCP 配置**：默认路径在 `atribot\LLMchat\MCP\mcp_server.json`，可通过 `"active": false` 控制特定 MCP 工具是否启用。
5.  **skills 文件夹**：默认路径在 `atribot\LLMchat\skills\agent_skills`
6.  根目录 `document\` 下可按项目结构放置音频、表情包等资源文件
7.  关于bot发送的表情包需要在`document\img\emojis`文件夹下新建**文件名代表内部表情的文件夹**然后里面放上对应文件夹名称的表情包的图片(支持:'.jpg', '.jpeg', '.png', '.gif')然后LLM会在聊天中自然发送了(没有的表情包话可以来找我)

### 4. 启动项目
项目依赖 **Python 3.13** 环境，推荐使用 `uv` 管理依赖。

**使用 uv (推荐):**
先进入项目根目录
```bash
uv sync
uv run main.py
```

**使用 pip:**
```bash
pip install -r requirements-windows.txt
python main.py
```
Linux / macOS 请分别使用 `requirements-linux.txt`、`requirements-macos.txt`。

> ⚠️ **重要**：请务必在项目根目录执行启动命令，否则可能出现路径解析错误。

### 5. 使用 Docker 启动
仓库已经补齐了可直接运行的 `Docker Compose` 配置，默认会启动：
- `atri-db`：带 `pgvector` 的 PostgreSQL
- `atri-bot`：ATRI 主程序容器

首次使用前，至少确认两件事：
1. `assets/supplier_config.json` 中的模型接口可用。
2. NapCat 能连接到 `ws://宿主机IP:8888/websocket?access_token=你的token`，或者你按需改 `.env` / Compose 里的端口和 token。

推荐先复制一份环境变量文件：
```bash
cp .env.docker.example .env
```

然后直接启动：
```bash
docker compose up -d --build
```

查看日志：
```bash
docker compose logs -f app
docker compose logs -f db
```

停止并删除容器：
```bash
docker compose down
```

如果需要连数据库看表：
```bash
docker compose exec db psql -U postgres -d postgres
```

说明：
- 容器启动时会基于 `assets/config.json` 生成一份运行时配置，不会覆盖你原本的本地配置。
- 默认把宿主机的 `assets/`、`document/`、`log/`、`temp/` 挂进容器，便于直接改配置和保留运行数据。
- 内置 AI 沙盒默认只做镜像名覆盖；如果你还想让容器内再调用 Docker 沙盒，需要额外挂载 Docker Socket。

---
## 📂 项目结构

```text
ATRI-main/
├─main.py                       # 项目入口
├─pyproject.toml                # Python 项目依赖与构建配置
├─docker-compose.yml            # Docker Compose 启动配置
├─README.md / README.en.md      # 中英文说明文档
├─requirements-*.txt            # 各平台依赖导出文件
├─assets/                       # ⚙️ 配置文件、示例配置与 SQL 辅助脚本
├─atribot/                      # 核心代码
│  ├─bot_framework.py           # Bot 初始化与整体装配入口
│  ├─C/                         # C 扩展模块(没什么用，之前感觉py解析字符串太慢了整的,还需要编译真麻烦，现在感觉没必要)
│  ├─commands/                  # 💻 群聊命令实现
│  │  ├─audio/                  # 音频与 TTS 相关命令
│  │  ├─bromidic/               # 图片 / B 站等杂项功能命令
│  │  ├─interior/               # 内部管理与状态查询命令
│  │  └─test/                   # 实验性 / 测试命令
│  ├─common_utils/              # 通用工具函数
│  │  └─file/                   # 文件、图片、文本处理工具
│  ├─core/                      # 核心架构
│  │  ├─cache/                  # 上下文缓存与生命周期管理
│  │  ├─command/                # 命令系统与权限管理
│  │  ├─db/                     # 数据库连接与数据访问
│  │  ├─event_trigger/          # 事件处理
│  │  ├─network_connections/    # WebSocket 与消息收发
│  │  └─type/                   # 核心类型定义
│  ├─docs/                      # 开发过程中的文档与笔记
│  └─LLMchat/                   # 🧠 LLM 聊天与 Agent 能力
│     ├─character_setting/      # 人设预设
│     ├─discard_tools/          # 已废弃的工具
│     ├─MCP/                    # MCP 协议工具与配置
│     ├─memory/                 # 记忆系统
│     ├─model_api/              # 模型供应商接口
│     ├─RAG/                    # 检索增强生成逻辑
│     ├─sandbox/                # 沙盒
│     ├─skills/                 # skills 提示词相关模块
│     └─tools/                  # 函数调用工具集
├─docker/                       # 🐳 Docker 相关资源
│  ├─db/                        # 数据库初始化脚本与镜像文件
│  └─python/                    # Python 容器环境相关资源
├─document/                     # 🎨 运行时资源目录
   ├─audio/                     # 音频素材
   ├─file/                      # 通用文本 / 文件资源
   ├─img/                       # 图片资源
   │  ├─ATRI_qrcode/            # 二维码资源
   │  ├─emojis/                 # 表情包目录
   │  └─tmp/                    # 临时图片目录
   ├─video/                     # 视频资源
   └──temp/                     # 临时运行文件
```

---

## 🤝 参与贡献

欢迎提交 Issue、PR，或者直接提出改进建议(我个人用的项目真的有人会提交吗)
无论是修 Bug、补文档、优化架构，还是扩展新能力，都非常欢迎

---

<div align="center">
  
_私は、高性能ですから!_  
  
<img src="https://files.astrbot.app/watashiwa-koseino-desukara.gif" width="100"/>

❤️ ATRI-bot ❤️
</div>


