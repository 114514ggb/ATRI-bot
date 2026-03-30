<img src="./assets/ATRI-bot.png" width = "400" height = "400" alt="ATRI-bot" align="right" />
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

>_時よ止まれ、おまえは美しい_
>
> — *𝓐𝓣𝓡𝓘 -𝓜𝔂 𝓓𝓮𝓪𝓻 𝓜𝓸𝓶𝓮𝓷𝓽𝓼-*
>
项目Logo由[吖密](https://space.bilibili.com/1196260828)绘制  
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED.svg)](https://www.docker.com/)
[![NapCat](https://img.shields.io/badge/Backend-NapCat-green.svg)](https://github.com/NapNeko/NapCatQQ)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](./LICENSE)

</div>

---

<details>
<summary>📑 目录（点击展开）</summary>

- [📖 前言](#-前言)
- [✨ 项目核心功能](#-项目核心功能)
  - [🧠 深度 LLM 聊天集成](#-深度-llm-聊天集成)
  - [💻 类 Unix 命令系统](#-类-unix-命令系统)
  - [🛠️ 其他实用功能](#-其他实用功能)
- [🚀 快速开始 (How to Run)](#-快速开始-how-to-run)
  - [1. 前端连接 (NapCat)](#1-前端连接-napcat)
  - [2. 数据库配置 (PostgreSQL)](#2-数据库配置-postgresql)
  - [3. 模型与环境配置](#3-模型与环境配置)
  - [4. 启动项目](#4-启动项目)
  - [5. 使用 Docker 启动](#5-使用-docker-启动)
- [📂 项目结构](#-项目结构)
- [🏗️ 架构设计](#-架构设计)
  - [整体消息流](#整体消息流)
  - [🧠 LLM 聊天流程设计](#-llm-聊天流程设计)
  - [💾 记忆系统设计](#-记忆系统设计)
- [🤝 参与贡献](#-参与贡献)
- [📄 开源协议](#-开源协议)

</details>

---

## 📖 前言

来自萌新到处学习(抄袭，不对是集百家之长✨)做出来私用的神秘项目
主要是**按照自己的需求**编写一个专到狭窄的学习性质的项目(专注于提供一个深度定制化的群聊机器人体验),发出来是用来交流学习的
你可以在里面了解到以下这些技术实践：

- **完整的 LLM 聊天全链路**：从提示词构建、Function Calling、MCP 工具调用，到结构化 JSON 决策解析
- **两级记忆系统**：短期滑动上下文 + LLM 压缩摘要，以及基于 pgvector 的长期向量记忆
- **混合检索（Hybrid RAG）**：向量检索 + 全文检索（pgroonga）双路召回，RRF 融合 + 时间衰减评分
- **依赖注入架构**：基于单例 `DIContainer` 的服务解耦与管理，全异步设计

项目结构清晰，核心链路注释详细，适合想了解「如何从零搭建一个 LLM Bot」的同学参考

- [ATRI-bot官网:亚托莉.top](https://亚托莉.top/)

---

## ✨ 项目核心功能

一个基于 **NapCat** 对接、专注于群聊场景的 QQ Bot，所有能力均围绕群聊深度定制

### 🧠 深度 LLM 聊天集成

完全自主实现的 LLM 聊天全链路，从输入处理到输出决策全部可控：

- **全异步高并发**：回复流程完全异步，支持多供应商 Key 池轮询，多群并发场景下也能稳定运行。
- **结构化决策输出**：模型以 JSON 格式返回结构化决策（回复 / 更新画像 / 静默 / 调用工具），行为完全可控且易于扩展。
- **工具扩展能力**：支持 Function Calling、**MCP (Model Context Protocol)** 协议工具集，以及 **Skills** 自定义提示词。
- **两级记忆系统**：
  - *短期*：每个群 / 用户维护独立的滑动上下文窗口，超限时由 LLM 自动压缩摘要、无损续接。
  - *长期*：对话结束后提取关键事件，经 Embedding 向量化后存入 PostgreSQL（pgvector），检索时采用**向量 + 全文双路召回 + RRF 融合 + 时间衰减**评分，让 Bot 有个比较可靠的长期记忆。
  > 注：长期记忆聚焦于对话中的事件与偏好，不适用于存储长文档，对于聊天场景下已足够实用。
- **用户画像**：为每位用户维护称呼、关系、性格、偏好等画像文档，嵌入每次对话上下文，保证跨会话态度一致。
- **高可用降级**：主模型 API 出现异常时，自动按配置顺序切换到备用供应商和模型，保证有问必达。
- **拟人化交互**：
  - 自然发送表情包，支持分段回复模拟真实打字节奏。
  - 达到条件时主动融入群聊话题，而不只是被动等待 @。
  - 支持人设切换等基础功能。

### 💻 类 Unix 命令系统

在群里 `@bot` 后以 `/` 开头即可触发（例如 `@atri-bot /help --list`，需使用QQ的@而非直接输入名字）：

- **参数解析**：支持 `-` / `--` 参数风格，内置参数类型校验。
- **权限管理**：内置多级权限系统，支持拉黑或授予管理员权限，可在任意处理环节拒绝非法调用。
- **自动帮助文档**：通过装饰器声明参数描述后，`--help` 文档自动生成，无需手写。

### 🛠️ 其他实用功能

- **高性能关键词匹配**：关键词响应底层采用 **AC 自动机**，即使配置上万条规则也能保持毫秒级响应。
- **群成员变动提醒**：成员加入或退出时自动通知。
- **戳一戳互动**：被戳时不只会响应，还会「戳回去」。
- **稳健架构基础**：数据库连接池 + 消息队列，从容应对并发压力。

---

## 🚀 快速开始 (How to Run)

### 1. 前端连接 (NapCat)
首先需要一个能够与 QQ 通信的前端，推荐使用 NapCat：
- [NapCat 安装指南](https://napneko.github.io/guide/napcat)
- [NapCat 项目地址](https://github.com/NapNeko/NapCatQQ)
> *注：你也可以自己实现前端，只要能对接上即可。*

### 2. 数据库配置 (PostgreSQL)
项目当前仅支持 PostgreSQL 数据库。
1.  **安装数据库**：建议安装较新的 PostgreSQL 版本。[官方安装文档](https://www.postgresql.org/download/)
2.  **安装数据库插件**：
    - 必须安装 `pgvector`（向量检索）[pgvector 项目地址](https://github.com/pgvector/pgvector)
    - 必须安装 `pgroonga`（全文检索）[PGroonga 文档](https://pgroonga.github.io/)
3.  **数据库初始化**：
    项目提供了初始化 SQL 文件：`assets/PostgreSQL基础.sql`（开发版）和 `docker/db/info.sql`（Docker 初始化版）。
    进入数据库（Linux 示例）：
    ```bash
    sudo -u postgres psql
    ```
    然后按顺序执行对应 SQL 文件创建表结构。

### 3. 模型与环境配置

#### 🤖 嵌入模型 (Embedding)
推荐优先使用本地的 `Qwen3-Embedding-0.6B:F16`。当然你也可以接入其他 Embedding API（OpenAI 格式兼容），只是仓库里目前主要按 Ollama 的使用方式测试过。
推荐使用 [Ollama](https://ollama.com/) 进行本地部署：
```bash
ollama run Qwen3-Embedding-0.6B:F16
```

> **注意**：如果更换 Embedding 模型，之前构建的向量数据需要重新构建。

#### 🗣️ 语音合成 (TTS) - 可选
支持接入 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)。
实现 Bot 主动发送语音或通过命令调用语音功能，可以设置语速、情感等常用参数；当然前提是你已经准备好了自己的语音模型。  
使用前需要修改 `atribot/commands/audio/TTS.py` 中的参考音频路径，以及 GPT-SoVITS 接口端口地址。  
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

- **扩展性**：如需支持其他类型的沙盒（如 Web 沙盒、系统命令沙盒），可继承 `atribot/LLMchat/sandbox/sandbox_base.py` 中的基类并实现相应接口。
- **文件操作**：AI 上下文中能够看到的文件可以放到 Python 环境中进行简单处理。

#### ⚙️ 配置文件
在启动前，请务必检查 `assets` 目录中的配置：
1.  将 `config copy.json` 重命名为 `config.json` 并配置(记得查看"如何配置配置文件.py")。
2.  将 `supplier_config copy.json` 重命名为 `supplier_config.json` 并配置（模型供应商配置,支持任意opneAI兼容的）。
    ```bash
    cp "assets/config copy.json" assets/config.json
    cp "assets/supplier_config copy.json" assets/supplier_config.json
    ```
3.  **MCP 配置**：默认路径在 `atribot/LLMchat/MCP/mcp_server.json`，可通过 `"active": false` 控制特定 MCP 工具是否启用。
4.  **Skills 文件夹**：默认路径在 `atribot/LLMchat/skills/agent_skills`。
5.  根目录 `document/` 下可按项目结构放置音频、表情包等资源文件。
6.  **表情包**：在 `document/img/emojis` 文件夹下新建**文件名代表内部表情的文件夹**，放入对应名称的图片（支持 .jpg, .jpeg, .png, .gif），LLM 即可在聊天中自然发送。


### 4. 启动项目
项目依赖 **Python 3.13** 环境，推荐使用 `uv` 管理依赖。

**使用 uv (推荐):**
```bash
# 进入项目根目录
uv sync
uv run main.py
```

**使用 pip:**
Linux / macOS 请分别使用 `requirements-linux.txt`、`requirements-macos.txt`。
```bash
pip install -r requirements-windows.txt
python main.py
```

> ⚠️ **重要**：请务必在项目根目录执行启动命令，否则可能出现路径解析错误。

### 5. 使用 Docker 启动
仓库已经补齐了可直接运行的 `Docker Compose` 配置，默认会启动：
- `atri-db`：带 `pgvector + pgroonga` 的 PostgreSQL
- `atri-bot`：ATRI 主程序容器

首次使用前，至少确认两件事：
1. `assets/supplier_config.json` 中的模型接口可用。
2. NapCat 能连接到 `ws://宿主机IP:8888/websocket?access_token=你的token`。

**推荐先复制一份环境变量文件：**
```bash
cp .env.docker.example .env
```
> **注意**：请检查 `.env` 文件中的端口与 Token 设置，确保与 NapCat 配置一致。

然后直接启动：
```bash
docker compose up -d --build
```

如果你已经跑过旧版本数据库结构，升级后建议先清理旧数据卷再重建：
```bash
docker compose down -v
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
├─assets/                       # ⚙️ 配置文件、示例配置
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

## 🏗️ 架构设计

### 整体消息流

```
NapCat (QQ客户端)
      │  WebSocket
      ▼
WebSocketClient (单例，消息队列)
      │
      ▼
message_router.main()
      │
      ├──► EventTrigger       (关键词/戳一戳/群成员变动等事件)
      ├──► CommandSystem       (@bot /cmd 命令)
      └──► LLMCoordinator      (LLM 聊天主流程)
```

因为是专门用来聊天的，只关心必要的消息处理不需要插件系统或其他复杂什么的过度设计,先简单过滤只处理群相关的消息简单分为@和其他,@就是区分命令和聊天,其他就会分发到一个简单的分发处理器EventTrigger

---

### 🧠 LLM 聊天流程设计

LLM 聊天的核心链路在 `atribot/LLMchat/` 目录下，整体采用**全异步流水线**设计：

```
用户消息 (ChatMessage)
      │
      ▼
chat.py → GroupChat.step()          ← 聊天主入口
      │
      ├─① prompt_structure()        构建提示词
      │     ├─ 群聊历史 (近期消息窗口)
      │     ├─ 用户画像 (UserSystem)
      │     ├─ 最近记忆片段 (memorySystem.query_user_recently_memory)
      │     ├─ 表情包提示词 (EmojiCore)
      │     └─ Skills 提示词 (SkillsManager)
      │
      ├─② LLMCoordinator.run()      调度模型请求
      │     ├─ 主模型请求 (model_api)
      │     ├─ Function Calling 循环 (MCP/tools)
      │     └─ 主模型失败时降级备用模型 (_request_model_with_fallback_)
      │
      ├─③ 解析 JSON 响应            模型输出结构化决策
      │     ├─ "reply"    → 回复消息 (分段发送 / 表情包)
      │     ├─ "update"   → 更新用户画像
      │     ├─ "silence"  → 不回复
      │     └─ "use_tools"→ 调用工具
      │
      └─④ 事后处理
            ├─ 上下文写回 (ChatManager)
            └─ 上下文超长时触发 summarize_context() 压缩
```

**高可用降级机制**：当主模型 API 响应异常时，`_request_model_with_fallback_` 会按照 `config.model.standby_model` 列表依次尝试备用供应商和模型，保证即使主力 Key 失效也能正常回复。

**结构化输出**：模型被要求返回 JSON 格式的决策列表（`return` 数组），每一项包含 `decision` 字段，使回复行为完全可控和可扩展。

---

### 💾 记忆系统设计

记忆系统分为**短期上下文缓存**和**长期向量记忆**两层：

#### 短期上下文 (ChatManager)
- 每个群/用户维护一个滑动的消息窗口 `Context`，直接嵌入每次请求的 `messages` 列表。
- 当上下文 token 数超限时，触发 `memorySystem.summarize_context()` 对旧消息进行 LLM 压缩摘要，压缩后的文本以 `assistant` 角色消息插入上下文头部，简单的进行记忆压缩。

#### 长期向量记忆 (memorySystem + pgvector)

```
聊天结束后
      │
      ▼
memorySystem.extract_stored_group_message()
      │
      ├─ LLM 信息提取 (PURE_GROUP_FACT_RETRIEVAL_PROMPT)
      │     └─ 输出结构化 JSON：per-user 事件 + 群话题
      │
      ├─ RAGManager.calculate_embedding()   文本 → 1024维向量
      │
      └─ MemoryVectorStore.batch_add_memories()  写入 PostgreSQL atri_memory 表
```

**记忆分类 (MemoryCategory)**：

| 分类 | 含义 | 时间半衰期 |
|------|------|-----------|
| `preference` | 用户偏好 | 90 天 |
| `fact` | 事实性记忆（默认） | 90 天 |
| `experience` | 经历记忆 | 60 天 |
| `emotion` | 情感记忆 | 30 天 |
| `group_topic` | 群聊话题 | 7 天 |
| `knowledge` | 通用知识 | ~10 年 |
| `domain` | 领域专业知识 | ~10 年 |
| `guideline` | 行为准则 | ~10 年 |

**混合召回 (hybrid_recall)**：使用一条带 CTE 的 SQL 同时进行**向量检索**（pgvector 余弦距离）和**全文检索**（pgroonga），再通过 RRF（Reciprocal Rank Fusion）融合两路结果，最终叠加重要度、访问频次和时间衰减进行综合排序。

```
查询文本
    │
    ├─ pgvector 向量路     (余弦距离，取前 40 候选)
    ├─ pgroonga 全文路     (全文评分，取前 40 候选)
    │
    └─ RRF 融合
           + importance / 10.0     × 权重
           + ln(1 + access_count)  × 权重
           + EXP(-λ × age_days)    × 时间衰减 (λ 按 category 差异化)
           │
           └─► 返回 Top-N 记忆
```

**用户画像 (UserSystem)**：为每个用户维护一份 JSON 画像文档（称呼、关系、性格、近期话题、偏好风格等），在每次对话的 prompt 中嵌入，确保 Bot 对同一用户的态度前后一致，画像由 LLM 在对话后自动更新。

---

## 🤝 参与贡献

欢迎提交 Issue、PR，或者直接提出改进建议。
无论是修 Bug、补文档、优化架构，还是扩展新能力，都非常欢迎。

## 📄 开源协议

本项目遵循 **GNU General Public License v3.0 (GPLv3)** 协议。
详情请参阅 [LICENSE](./LICENSE) 文件。

---

<div align="center">
  
_私は、高性能ですから!_  
  
<img src="https://files.astrbot.app/watashiwa-koseino-desukara.gif" width="100"/>

❤️ ATRI-bot ❤️
</div>
