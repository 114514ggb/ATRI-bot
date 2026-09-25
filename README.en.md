<img src="./assets/ATRI-bot.png" width="400" height="400" alt="ATRI-bot" align="right" />
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
> — **𝓐𝓣𝓡𝓘 -𝓜𝔂 𝓓𝓮𝓪𝓻 𝓜𝓸𝓶𝓮𝓷𝓽𝓼-**
>
Logo illustrated by [吖密](https://space.bilibili.com/1196260828)  
[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED.svg)](https://www.docker.com/)
[![NapCat](https://img.shields.io/badge/Backend-NapCat-green.svg)](https://github.com/NapNeko/NapCatQQ)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.4-orange.svg)](./pyproject.toml)

</div>

---

<details>
<summary>📑 Table of Contents (click to expand)</summary>

- [📖 Introduction](#-introduction)
- [✨ Core Features](#-core-features)
  - [🧠 Deep LLM Chat Integration](#-deep-llm-chat-integration)
  - [💻 Unix-like Command System](#-unix-like-command-system)
  - [🖥️ Web Admin Panel](#-web-admin-panel)
  - [🛠️ Other Practical Features](#-other-practical-features)
- [🚀 Quick Start (How to Run)](#-quick-start-how-to-run)
  - [1. Frontend Connection (NapCat)](#1-frontend-connection-napcat)
  - [2. Database Configuration (PostgreSQL)](#2-database-configuration-postgresql)
  - [3. Model & Environment Configuration](#3-model--environment-configuration)
  - [4. Start the Project](#4-start-the-project)
  - [5. Run Tests](#5-run-tests)
  - [6. Docker Deployment](#6-docker-deployment)
- [📂 Project Structure](#-project-structure)
- [🏗️ Architecture Design](#-architecture-design)
  - [Message Flow Overview](#message-flow-overview)
  - [🧠 LLM Chat Pipeline](#-llm-chat-pipeline)
  - [💾 Memory System Design](#-memory-system-design)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

</details>

---

## 📖 Introduction

A personal hobby project created by a beginner learning (or rather, "combining the strengths of many" ✨) from various sources.
It is primarily a **highly customized** learning-oriented project (focused on providing a deeply tailored group chat bot experience), shared here for exchange and learning purposes.

You can learn the following technical practices from this project:

- **Complete LLM Chat Pipeline**: From prompt construction, Function Calling, MCP tool invocation, to structured JSON decision parsing.
- **Two-tier Memory System**: Short-term sliding context + LLM compression summaries, and pgvector-based long-term vector memory.
- **Hybrid RAG**: Vector retrieval + full-text search (pgroonga) dual-path recall, RRF fusion + time-decay scoring.
- **Dependency Injection Architecture**: Singleton `DIContainer`-based service decoupling and management, fully asynchronous design.

The codebase is well-structured with detailed comments in core pipelines — suitable for those interested in "how to build an LLM Bot from scratch".

- [ATRI-bot Official Site: 亚托莉.top](https://亚托莉.top/)

---

## ✨ Core Features

A **NapCat**-connected QQ Bot deeply customized for group chat scenarios, with full private chat support as well.

### 🧠 Deep LLM Chat Integration
Fully self-implemented LLM chat pipeline with complete control from input processing to output response:
- **Fully asynchronous & high concurrency**: The reply process is completely asynchronous, supporting key pool rotation, easily handling high-concurrency scenarios across multiple group chats.
- **Self-controllable**: Supports function calling and **MCP (Model Context Protocol)** configuration. The model returns structured JSON decisions (`speak` / `update` / `silence`), and 18 built-in tools are available (web search, memory read/write, sandboxed Python/Shell execution, sub-agent, scheduled self-trigger, tool discovery, etc.), with `tool_search` discovering `deferred` tools on demand (see `config.tool_presets`).
- **RAG Memory System**: Memory function based on RAG (Retrieval-Augmented Generation), supporting knowledge base Q&A, giving the bot "long-term memory".
- **LaTeX formula rendering**: Formulas in replies (`$...$`, `$$...$$`, `\(...\)`, `\[...\]`) are automatically rendered as images before sending, so discussing math in chat doesn't mean a wall of raw source code.
- **High availability design**: Implements fallback API response mechanism. If the primary model responds with an error, it automatically downgrades to other configured models (may be slower but ensures responses).
- **Human-like interaction**:
  - Naturally sends emojis/stickers.
  - Simulates human speaking habits, supports segmented message sending.
  - **Active topic participation**: Under certain conditions, it will attempt to actively reply to group messages and join conversations.
  - **User profile maintenance**: Maintains User documents for embedding context, ensuring consistent attitude toward the same user.
  - Supports basic functions like persona switching.

### 💻 Unix-like Command System
Features a usable command mechanism. Trigger by mentioning the bot followed by `/` in the group (e.g., `@atri-bot /help --list`—must use the actual QQ @, not plain text):
- **Argument parsing**: Supports `-` and `--` argument styles with built-in type validation.
- **Permission management**: Built-in permission system supporting blacklisting and granting admin rights. Can validate User permissions at any processing stage to reject unauthorized execution.
- **Auto-generated help**: Simply use decorators in code and add argument descriptions to automatically generate detailed `--help` prompts.

### 🖥️ Web Admin Panel

A web admin panel runs as an in-process background task when the bot starts (same process, bound to `127.0.0.1`, route prefix `/admin/`; `web_panel.enable` is on by default; port and login token are configured in `config.web_panel`, port falls back to `5125` when unset, this repo uses `5308`). Panel failures do not affect the bot's main service:

- **Visual management**: Online config editing (model suppliers, MCP tools, etc.), database status, memory browsing, persona switching, log viewing, and more — all adapted for mobile browsers.
- **Web chat**: A built-in chat page lets you talk to the bot directly in the browser, with multi-session management, streaming agent output, attachment uploads, and a dedicated `webui` tool preset (`default` loaded by default / `deferred` loaded on demand).
- **Security**: `access_token` authentication with rate limiting on repeated failures to prevent brute-force attacks.

### 🛠️ Other Practical Features
- **Plugin system**: Plugins under `atribot/plugins/` are auto-loaded at startup, supporting message/notice/request event subscriptions and pipeline middleware, with explicit hot-reload (`PluginManager.reload_plugin`).
- **Sub-agent collaboration**: The `sub_agent` tool can delegate complex multi-step tasks to an independent sub-agent (own toolset + LLM loop).
- **Scheduled self-trigger**: The `schedule_self_trigger` tool lets the bot proactively start a new group chat thinking at a specified time.
- **High-performance keyword matching**: Configuration files support keyword responses, using the **AC Automaton** algorithm underneath for millisecond-level response even with tens of thousands of entries.
- **Group member change notifications**: Automatically notifies when someone joins or leaves the group.
- **Poke interaction**: Reacts when poked, may even "poke back".
- **Robust architecture**: Database uses connection pools, message reception introduces message queue mechanisms, maximizing stress resistance.

---

## 🚀 Quick Start (How to Run)

### 1. Frontend Connection (NapCat)
First, you need a frontend that can communicate with the QQ server. NapCat is recommended:  
[NapCat Installation Guide](https://napneko.github.io/guide/napcat)  
[NapCat Repository](https://github.com/NapNeko/NapCatQQ)
> *Note: You can also implement your own frontend, as long as it can connect properly.*

### 2. Database Configuration (PostgreSQL)
The project only supports PostgreSQL.
1.  **Install PostgreSQL**: Recommended a recent version. [Official Installation Docs](https://www.postgresql.org/download/)
2.  **Install database extensions**:
    - Must install the `pgvector` extension for vector search. [pgvector Extension](https://github.com/pgvector/pgvector)
    - Must install the `pgroonga` extension for full-text search. [PGroonga Docs](https://pgroonga.github.io/)
3.  **Database initialization**:
    The project provides an initialization SQL file: `docker/db/info.sql` (recommended, includes full schema and extension setup).  
    Access the database (Linux example):
    ```bash
    sudo -u postgres psql
    ```
    Then execute the contents of `info.sql` in order to create the table structure.

### 3. Model & Environment Configuration
#### 🤖 Embedding Model
It is recommended to use the local `dengcao/Qwen3-Embedding-0.6B:F16`. Paid API alternatives are also possible (only tested with Ollama).  
Recommended deployment via [Ollama](https://ollama.com/):
```bash
ollama run dengcao/Qwen3-Embedding-0.6B:F16
```
> **Note**: If you change the Embedding model, previously built vector data needs to be rebuilt.
#### 🗣️ Text-to-Speech (TTS) - Optional
Supports integration with [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) to enable the bot to send voice messages or invoke TTS via commands, with configurable parameters like speed and emotion. You will also need your own voice model.
Before use, modify `atribot/commands/audio/TTS.py` to set the reference audio path and GPT-SoVITS API port address:
```json
{
    "emotion_name_here": {
        "refer_wav_path": "full_path_to_reference_audio",
        "prompt_text": "corresponding_text_for_reference_audio",
        "prompt_language": "language_of_reference_text"
    },
    "calm": {
        "refer_wav_path": "/home/atri/音乐/tts_reference/夏生さんが望むのでしたら.mp3",
        "prompt_text": "夏生さんが望むのでしたら",
        "prompt_language": "ja"
    }
}
```


#### 📦 Sandbox Environment (Optional)

Equips the AI model with a default **code sandbox environment** to safely execute user-requested or self-generated code snippets. The default implementation uses a **Docker** 🐳-based sandbox (switchable via `sand_box.type` to local execution (`none` / `no_sandbox` / `local`) or the E2B cloud sandbox), supporting languages like Python, useful for code interpretation, data calculation, etc. The image (`sand_box.image`) ships with numpy/pandas/matplotlib/seaborn/opencv/scipy/sympy, ffmpeg and CJK fonts; tool descriptions adapt to backend/OS/shell, and `sand_box.tool_prompts` / `sand_box.tools` can override or disable individual tools.

- **Extensibility**: To support other sandbox types (e.g., web sandbox, system command sandbox), inherit from the base class in `atribot/LLMchat/sandbox/sandbox_base.py` and implement the corresponding interface.
- **File Operations**: Files visible in the AI context can be placed into the Python environment for simple processing.

#### ⚙️ Configuration Files
Before starting, ensure to check the  `assets` folder:
1.  Refer to `assets\如何配置配置文件.md` (Chinese guide) for configuration details.
2.  **Platform connection**: `config.platforms.<name>` configures the connection to NapCat (`adapter` fixed as `onebot`, `connection_type` supports `WebSocket_client` / `WebSocket_server` / `http`, `access_token` must match NapCat, `url` is the address).
3.  Configure `supplier_config.json` (model supplier settings).
4.  Configure `config.json` (project basic settings).
5.  **MCP Configuration**：Default path is `atribot\LLMchat\MCP\mcp_server.json`. Specific MCP tools can be toggled via `"active": false`; remote servers use SSE by default, set `"transport": "streamable_http"` to use Streamable HTTP.
6.  Under root `document/`, you can add corresponding audio, emoji, and file configurations according to the project structure.
7.  **Web admin panel**: `config.web_panel` controls the admin panel (`enable` on by default, `port` falls back to `5125` when unset (this repo uses `5308`), `access_token` is the login token — make sure to change it after deployment; the token can also be provided via the `ATRI_PANEL_TOKEN` env var).
8.  **Path mapping**: When the bot and the protocol frontend (NapCat) run on different filesystems (e.g. bot in WSL, NapCat on Windows), configure a "local path prefix → frontend path prefix" mapping in `file_path.path_mapping` (e.g. `"E:/": "/mnt/e/"`); `file://` paths are converted automatically when sending. Leave empty to disable.
### 4. Start the Project
The project requires **Python 3.14**. Using `uv` for package management is recommended.

**Using uv (recommended):**
```bash
# Enter the project root directory
uv sync
uv run main.py
```

**Using pip:**
Use `requirements-linux.txt` or `requirements-macos.txt` on Linux / macOS respectively.
```bash
pip install -r requirements-windows.txt
python main.py
```
> ⚠️ **Important**: Ensure you are in the project root directory when running these commands to avoid path errors.

### 5. Run Tests
The project uses `pytest` with async mode enabled by default.
```bash
# Using uv
uv run pytest

# Or directly
python -m pytest tests/
```

### 6. Docker Deployment
The repository includes a ready-to-run `Docker Compose` configuration that starts:
- `atri-db`: PostgreSQL with `pgvector + pgroonga`
- `atri-bot`: ATRI main application container

Before first use, ensure:
1. Model API in `assets/supplier_config.json` is accessible.
2. NapCat can connect to `ws://host-ip:8888/websocket?access_token=your-token`.

**Copy the environment file first:**
```bash
cp .env.docker.example .env
```
> **Note**: Check the ports and token settings in `.env` to match your NapCat configuration.

**Environment Variables** (`.env.docker.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `ATRI_DB_SUPERUSER_PASSWORD` | PostgreSQL superuser password | `180710` |
| `ATRI_DB_NAME` | Application database name (written into `database.database` of the runtime config) | `atri` |
| `ATRI_DB_APP_USER` | Application database user | `atri` |
| `ATRI_DB_APP_PASSWORD` | Application database password | `180710` |
| `ATRI_DB_PORT_FORWARD` | Host port for the database (bound to 127.0.0.1 only) | `5432` |
| `ATRI_BOT_PORT` | Bot WebSocket service port | `8888` |
| `ATRI_ACCESS_TOKEN` | NapCat connection token | `ATRI114514` |
| `ATRI_NAPCAT_URL` | NapCat WebSocket URL (client mode only) | `host.docker.internal:3001` |
| `ATRI_PANEL_PORT` | Web admin panel port (inside the container equals the host mapping) | `5308` |
| `ATRI_PANEL_TOKEN` | Web admin panel token (⚠️ overridden by `web_panel.access_token`, see below) | empty |
| `ATRI_SANDBOX_IMAGE` | AI sandbox image (build it manually first, see section 4) | `atri-sandbox:latest` |
| `ATRI_FILE_LOG` | `1` = also write file logs, `0` = stdout only | `1` |
| `TZ` | Container timezone | `Asia/Shanghai` |

Then start:
```bash
docker compose up -d --build
```

If you have run older database structures, it's recommended to clear old data volumes before rebuilding:
```bash
docker compose down -v
docker compose up -d --build
```

View logs:
```bash
docker compose logs -f app
docker compose logs -f db
```

Stop and remove containers:
```bash
docker compose down
```

Connect to the database:
```bash
docker compose exec db psql -U postgres -d postgres
```

**Access the Web admin panel** (the container listens on `0.0.0.0`, port equals `ATRI_PANEL_PORT`):
```
http://localhost:5308/admin/
```
The token is `web_panel.access_token` in `assets/config.json` (currently the weak value `ATRI` — **change it before deploying**). To make `ATRI_PANEL_TOKEN` from `.env` effective, remove `access_token` from the config file first (it has higher priority).

**⚠️ Path mapping (required for Docker)**: when sending local media, the bot hands NapCat a `file://` path **inside the container** (e.g. `/app/document/...`), which the host NapCat cannot read. Configure `assets/config.json` on the host:
```json
"file_path": {
    "path_mapping": {
        "/app/document": "<absolute path of the host document directory>",
        "/app/assets": "<absolute path of the host assets directory>"
    }
}
```
Typical symptoms without it: TTS voice, emoji, local images/files fail to send (NapCat reports the file does not exist).

**Stop & graceful shutdown**: the app container uses `stop_signal: SIGINT` (Python's graceful shutdown is wired to the Ctrl+C path; SIGTERM kills the process immediately) plus a 30s grace period:
```bash
docker compose stop app        # graceful stop (panel, DB pool and sandbox containers are cleaned up)
docker compose down            # stop and remove containers
docker compose down -v         # also remove the data volume (recreate the database)
```

Notes:
- The container generates a runtime config based on `assets/config.json` without overwriting your local setup.
- Host directories `assets/`, `document/`, `atribot/log/` and `temp/` are mounted into the container; file logs are written to `atribot/log/` (`ATRI_FILE_LOG=0` switches to stdout-only so Docker log rotation handles them).
- The sandbox only overrides the image name, so build the sandbox image **manually first** (`docker build -t atri-sandbox:latest -f atribot/LLMchat/sandbox/Dockerfile .`). Without it the bot still starts, but AI code execution is unavailable. Compose mounts the Docker socket (`/var/run/docker.sock`), so the sandbox can talk to the host Docker daemon out of the box.
- The image ships `uv` (for `uvx`) and Node.js (for `npx`), so stdio MCP servers work out of the box; use `docker build --build-arg WITH_NODE=0` to drop Node and shrink the image.
- ⚠️ Security: the default credentials (DB `180710`, platform token `ATRI114514`, panel token `ATRI`) are public weak values — change them; mounting `/var/run/docker.sock` grants host root access to the container, so never expose the panel/ports to the public internet.

---
## 📂 Project Structure

```text
ATRI-main/
├─main.py                       # Project entry point
├─pyproject.toml                # Python project dependencies & build config
├─docker-compose.yml            # Docker Compose startup config
├─.env.docker.example           # Docker environment variables template
├─README.md / README.en.md      # Chinese / English documentation
├─requirements-*.txt            # Platform-specific dependency exports
├─tests/                        # 🧪 Unit & integration tests
├─assets/                       # ⚙️ Configuration files & examples
├─atribot/                      # Core code
│  ├─bot_framework.py           # Bot initialization & assembly entry point
│  ├─C/                         # C extension modules (Levenshtein algorithm, etc.)
│  ├─commands/                  # 💻 Group chat command implementations
│  │  ├─audio/                  # Audio & TTS commands
│  │  ├─bromidic/               # Image processing / token query & miscellaneous commands
│  │  ├─interior/               # Internal management & status commands
│  │  └─test/                   # Experimental / test commands
│  ├─common_utils/              # Common utility functions
│  │  └─file/                   # File, image, text processing tools
│  ├─core/                      # Core architecture
│  │  ├─cache/                  # Context cache & lifecycle management
│  │  ├─command/                # Command system & permission management
│  │  ├─db/                     # Database connection & data access
│  │  ├─event_bus/              # Event bus (dispatch by PostType)
│  │  ├─pipeline/               # Middleware pipeline (incl. group whitelist)
│  │  ├─platform/               # Multi-platform adapter layer
│  │  ├─network_connections/    # Legacy WebSocket client base (sending goes through SendClientBase / PlatformManager)
│  │  └─type/                   # Core type definitions (event envelope / segments)
│  ├─docs/                      # Development notes & documentation
│  ├─LLMchat/                   # 🧠 LLM chat & Agent capabilities
│  │  ├─character_setting/      # Character presets
│  │  ├─discard_tools/          # Deprecated tools
│  │  ├─MCP/                    # MCP protocol tools & configuration
│  │  ├─memory/                 # Memory system
│  │  ├─model_api/              # Model supplier interfaces
│  │  ├─RAG/                    # Retrieval-Augmented Generation logic
│  │  ├─sandbox/                # Sandbox
│  │  ├─skills/                 # Skills prompt modules
│  │  └─tools/                  # Function calling toolset (18 tools: 13 dir tools + sub_agent + 4 sandbox tools)
│  ├─plugins/                   # 🔌 Plugin system
│  │  ├─plugin.py               # Plugin base class (event / middleware decorators)
│  │  ├─manager.py / loader.py / runtime.py / registry.py # Plugin management, loading (hot-reload) & runtime mounting
│  │  ├─emoji_like/             # Message emoji mirror
│  │  ├─group_manager/          # Group management + keyword replies + join approval
│  │  └─poke_reaction/          # Poke feedback
│  ├─log/                       # Runtime logs (daily rotation, 7 days)
│  └─web_panel/                 # 🖥️ Web admin panel
│     ├─panel_router.py         # Panel routing & static assets
│     ├─deps.py                 # Auth / config shared dependencies
│     ├─dev_server.py / API.md  # Dev server (mock env) & API docs
│     ├─routes/                 # Backend endpoints (chat / config / database / memory / personas / ...)
│     ├─templates/              # Page templates
│     └─static/                 # Frontend assets (JS / CSS)
├─docker/                       # 🐳 Docker resources
│  ├─db/                        # Database init scripts & images
│  └─python/                    # Python container environment
├─document/                     # 🎨 Runtime resource directory
│  ├─audio/                     # Audio assets
│  ├─file/                      # Generic text / file resources
│  ├─img/                       # Image assets
│  │  ├─ATRI_qrcode/            # QR code resources
│  │  └─emojis/                 # Emoji/sticker directory
│  ├─video/                     # Video assets
│  ├─work/                      # Local sandbox (local backend) workspace
│  └─temp/                      # Temporary runtime files
├─privacy/                      # Development notes & private files
```

---

## 🏗️ Architecture Design

### Message Flow Overview

```
NapCat (QQ Client)
      │  WebSocket / HTTP
      ▼
Platform Adapter (OneBotAdapter, multi-platform)
      │
      ▼
MessageQueue (message queue)
      │
      ▼
Pipeline (WhitelistMiddleware group whitelist filtering + ChatManager context injection)
      │
      ▼
EventBus (dispatch by PostType)
      │
      ├──► Message storage listener (priority=101, persists to message table)
      ├──► AtCommandRule route  (@bot /cmd commands → CommandSystem)
      ├──► Plugin event handlers (Plugin.on_message / on_notice, etc.)
      └──► Chat route (priority=100: group initiativeChat / private privateChatTrigger → LLM decision)
```

Group chats are handled by `GroupChat`, private chats by `PrivateChat`. The command and chat routes are registered in `bot_framework._register_at_routes()`; the whitelist middleware and message storage are wired by `_register_message_storage()` (storage listener priority 101 runs before the chat route at 100); plugin handlers are auto-scanned and mounted by `PluginManager` at startup.

Besides the message backbone, the `web_panel/` module runs a visual admin & chat panel as an in-process background task (uvicorn bound to `127.0.0.1`, route prefix `/admin/`) — panel failures never affect the bot's main service.

---

### 🧠 LLM Chat Pipeline

The core LLM chat pipeline resides in `atribot/LLMchat/` and follows a **fully asynchronous pipeline** design:

```
User Message (MessageEventEnvelope)
      │
      ▼
chat.py → GroupChat.step()          ← Chat entry point
      │
      ├─① prompt_structure()        Build prompt
      │     ├─ Group chat history (recent message window)
      │     ├─ User profile (UserSystem)
      │     ├─ Recent memory snippets (MemorySystem.query_user_recently_memory)
      │     ├─ Emoji prompts (EmojiCore)
      │     └─ Skills prompts (SkillsManager)
      │
      ├─② LLMCoordinator.run()      Dispatch model request
      │     ├─ Primary model request (model_api)
      │     └─ Function Calling loop (MCP/tools)
      │
      ├─③ Parse JSON response       Model outputs structured decisions
      │     ├─ "speak"    → Send response via MessageSender (segmented / with emojis)
      │     ├─ "update"   → Update user profile
      │     ├─ "silence"  → No reply
      │     └─ tool calls → Via Function Calling loop (MCP / local tools)
      │
      └─④ Post-processing
            ├─ Context write-back (ChatManager)
            └─ Trigger summarize_context() when context exceeds token limit
```

**High-Availability Fallback**: When the primary model API returns an error, the request wrappers of `GroupChat`/`PrivateChat` in `chat.py` (`_request_model_with_fallback_` / `_request_model_with_fallback_private_`) iterate through the `config.model.standby_model` list to try backup providers and models (including vision-capability differences), ensuring responses even when the primary key fails.

**Structured Output**: The model is instructed to return a JSON object (with an `actions` array), each item containing a `decision` field (`speak` / `update` / `silence`), making response behavior fully controllable and extensible.

---

### 💾 Memory System Design

The memory system consists of two layers: **short-term context cache** and **long-term vector memory**.

#### Short-term Context (ChatManager)
- Each group/user maintains a sliding message window `Context`, directly embedded into each request's `messages` list.
- When the context exceeds the token limit, `MemorySystem.summarize_context()` triggers LLM-based compression of older messages. The compressed summary is inserted as an `assistant` role message at the head of the context.

#### Long-term Vector Memory (MemorySystem + pgvector)

```
After chat ends
      │
      ▼
MemorySystem.extract_stored_group_message()
      │
      ├─ LLM Information Extraction (PURE_GROUP_FACT_RETRIEVAL_PROMPT)
      │     └─ Output: structured JSON — per-user events + group topics
      │
      ├─ RAGManager.calculate_embedding()   Text → 1024-dim vector
      │
      └─ MemoryVectorStore.batch_add_memories()  Write to PostgreSQL atri_memory table
```

**Memory Categories (MemoryCategory)**:

| Category | Meaning | Half-life |
|----------|---------|-----------|
| `preference` | User preferences | 90 days |
| `fact` | Factual memory (default) | 90 days |
| `experience` | Experiential memory | 60 days |
| `emotion` | Emotional memory | 30 days |
| `group_topic` | Group chat topics | 7 days |
| `knowledge` | General knowledge | ~10 years |
| `domain` | Domain expertise | ~10 years |
| `guideline` | Behavioral guidelines | ~10 years |

**Hybrid Recall**: A single CTE-based SQL query performs both **vector retrieval** (pgvector cosine distance) and **full-text retrieval** (pgroonga), then fuses results via RRF (Reciprocal Rank Fusion), with final ranking by importance, access frequency, and time decay. Retrieval columns are indexed, keeping memory queries fast as data grows.

```
Query text
    │
    ├─ pgvector vector path     (cosine distance, top 40 candidates)
    ├─ pgroonga full-text path  (full-text score, top 40 candidates)
    │
    └─ RRF fusion
           + importance / 10.0     × weight
           + ln(1 + access_count)  × weight
           + EXP(-λ × age_days)    × time decay (λ varies by category)
           │
           └─► Return Top-N memories
```

**Memory Auto-Update & Evolution (Memory Consolidator)**:
The system not only supports writing and extraction, but also maintains fragmented pieces and resolves conflicting information continuously:

```
Periodic maintenance / New memory extraction
      │
      ▼
Conflict Detection & Clustering (Cluster Utils)
      │
      ├─ Similarity graph construction (pgvector-based high-similarity edges)
      ├─ Connected component clustering (group similar memories by user)
      │
      └─ Sequential safe processing
             ├─ LLM content merging (resolve conflicts / expand information)
             ├─ update_memory (inherit highest weights, update vectors)
             └─ batch_delete (remove redundant fragments)
```

- **Dynamic Memory Updates**: Beyond simple appending, when newly extracted memories conflict with or extend existing ones, the system invokes LLM to update content and attributes, breaking the append-only limitation.
- **Background Defragmentation**: A scheduled maintenance task clusters recently active, highly similar memories using connected graph analysis, then safely merges and deduplicates them via LLM, preventing redundant information buildup; the facade also exposes `cleanup_expired_memories()` / `consolidate_memories()` for manual maintenance.
- **Dynamic Cleanup**: Based on memory categories and their distinct half-life configurations, expired memories are automatically purged on schedule — highly active group topics and daily scattered memories lose relevance naturally.

**User Profiles (UserSystem)**: A JSON profile document (name, relationship, personality, recent topics, style preferences, etc.) is maintained for each user and embedded into every conversation prompt, ensuring the bot's attitude toward the same user remains consistent. Profiles are automatically updated by the LLM after each conversation.

---

## 🤝  Contributing

You are very welcome to contribute to this project! Whether it's reporting bugs, fixing code, or suggesting new features.
Let's make ATRI smarter and cuter together!
(Though it’s still quite rough at the moment.)

---
## 📄 License

This project is licensed under the **MIT License**.
See the [LICENSE](./LICENSE) file for details.

---<div align="center">
  
_私は、高性能ですから!_  
  
<img src="https://files.astrbot.app/watashiwa-koseino-desukara.gif" width="100"/>

❤️ ATRI-bot ❤️
</div>
