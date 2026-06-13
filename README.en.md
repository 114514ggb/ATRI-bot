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
项目Logo由[吖密](https://space.bilibili.com/1196260828)绘制  
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
  - [🛠️ Other Practical Features](#-other-practical-features)
  - [🖥️ Web Admin Panel](#-web-admin-panel)
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

A **NapCat**-connected QQ Bot focused on group chat scenarios, with all capabilities deeply customized for group interactions.

### 🧠 Deep LLM Chat Integration
Fully self-implemented LLM chat pipeline with complete control from input processing to output response:
- **Fully asynchronous & high concurrency**: The reply process is completely asynchronous, supporting key pool rotation, easily handling high-concurrency scenarios across multiple group chats.
- **Self-controllable**: Supports function calling and **MCP (Model Context Protocol)** configuration.
- **RAG Memory System**: Memory function based on RAG (Retrieval-Augmented Generation), supporting knowledge base Q&A, giving the bot "long-term memory".
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

### 🛠️ Other Practical Features
- **High-performance keyword matching**: Configuration files support keyword responses, using the **AC Automaton** algorithm underneath for millisecond-level response even with tens of thousands of entries.
- **Group member change notifications**: Automatically notifies when someone joins or leaves the group.
- **Poke interaction**: Reacts when poked, may even "poke back".
- **Robust architecture**: Database uses connection pools, message reception introduces message queue mechanisms, maximizing stress resistance.

### 🖥️ Web Admin Panel

The project includes a lightweight web admin panel (built with FastAPI). Access it after startup at:

```
http://127.0.0.1:1314/admin/
```

- **Authentication**: Use the `access_token` (same as NapCat connection token) as a Bearer Token to log in.
- **Runtime Status**: View bot account info, current model, uptime, sandbox/MCP status, etc.
- **Data Statistics**: Group count, user count, message count, memory entry count at a glance.
- **Group Management**: Browse joined groups with pagination and search support.

> The panel listens on `127.0.0.1` by default for security. Do not expose it directly to the public internet. The port can be customized via `network.admin_port` in `config.json`.

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
It is recommended to use the local `Qwen3-Embedding-0.6B:F16`. Paid API alternatives are also possible (only tested with Ollama).  
Recommended deployment via [Ollama](https://ollama.com/):
```bash
ollama run Qwen3-Embedding-0.6B:F16
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
        "refer_wav_path": "/home/atri/tts_reference/夏生さんが望むのでしたら.mp3",
        "prompt_text": "夏生さんが望むのでしたら",
        "prompt_language": "ja"
    }
}
```


#### 📦 Sandbox Environment (Optional)

Equips the AI model with a default **code sandbox environment** to safely execute user-requested or self-generated code snippets. The current implementation uses a **Docker** 🐳-based sandbox supporting languages like Python, useful for code interpretation, data calculation, etc.

- **Extensibility**: To support other sandbox types (e.g., web sandbox, system command sandbox), inherit from the base class in `atribot/LLMchat/sandbox/sandbox_base.py` and implement the corresponding interface.
- **File Operations**: Files visible in the AI context can be placed into the Python environment for simple processing.

#### ⚙️ Configuration Files
Before starting, ensure to check the  `assets` folder:
1.  Refer to `assets\如何配置配置文件.py` (Chinese guide) for configuration details.
2.  Configure `supplier_config.json` (model supplier settings).
3.  Configure `config.json` (project basic settings).
4.  **MCP Configuration**：Default path is `atribot\LLMchat\MCP\mcp_server.json`. Specific MCP tools can be toggled via `"active": false`.
5.  Under root `document/`, you can add corresponding audio, emoji, and file configurations according to the project structure.
### 4. Start the Project
The project requires **Python 3.14**. Using `uv` for package management is recommended.

**Using uv (recommended):**
```bash
# Enter the project root directory
uv sync
uv run main.py
```

**Using pip:**
```bash
pip install -r requirements.txt
python3 main.py
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
| `ATRI_DB_NAME` | Application database name | `atri` |
| `ATRI_DB_APP_USER` | Application database user | `atri` |
| `ATRI_DB_APP_PASSWORD` | Application database password | `180710` |
| `ATRI_DB_PORT_FORWARD` | Host port mapping | `5432` |
| `ATRI_BOT_PORT` | Bot WebSocket service port | `8888` |
| `ATRI_ACCESS_TOKEN` | NapCat connection token | `ATRI114514` |
| `ATRI_CONNECTION_TYPE` | Connection type (WebSocket_server/client) | `WebSocket_server` |
| `ATRI_NAPCAT_URL` | NapCat WebSocket URL (client mode) | `host.docker.internal:3001` |
| `ATRI_SANDBOX_IMAGE` | AI sandbox Docker image | `python:3.13-slim` |
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

Notes:
- The container generates a runtime config based on `assets/config.json` without overwriting your local setup.
- Host directories `assets/`, `document/`, `log/`, `temp/` are mounted into the container for easy configuration and data persistence.
- AI sandbox only overrides the image name by default; to call Docker sandbox from within the container, you need to additionally mount the Docker socket.
- **Web Admin Panel**: After startup, access via `http://host-ip:1314/admin/` using the `ATRI_ACCESS_TOKEN` from `.env` as the Bearer Token.

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
│  │  ├─bromidic/               # Images / Bilibili & miscellaneous commands
│  │  ├─interior/               # Internal management & status commands
│  │  └─test/                   # Experimental / test commands
│  ├─common_utils/              # Common utility functions
│  │  └─file/                   # File, image, text processing tools
│  ├─core/                      # Core architecture
│  │  ├─cache/                  # Context cache & lifecycle management
│  │  ├─command/                # Command system & permission management
│  │  ├─db/                     # Database connection & data access
│  │  ├─event_trigger/          # Event handling
│  │  ├─network_connections/    # WebSocket & message I/O
│  │  └─type/                   # Core type definitions
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
│  │  └─tools/                  # Function calling toolset
│  └─web_panel/                 # 🖥️ Web admin panel
├─docker/                       # 🐳 Docker resources
│  ├─db/                        # Database init scripts & images
│  └─python/                    # Python container environment
├─document/                     # 🎨 Runtime resource directory
│  ├─audio/                     # Audio assets
│  ├─file/                      # Generic text / file resources
│  ├─img/                       # Image assets
│  │  ├─ATRI_qrcode/            # QR code resources
│  │  ├─emojis/                 # Emoji/sticker directory
│  │  └─tmp/                    # Temporary image directory
│  ├─video/                     # Video assets
│  └─temp/                      # Temporary runtime files
├─privacy/                      # Development notes & private files
└─log/                          # Runtime logs
```

---

## 🏗️ Architecture Design

### Message Flow Overview

```
NapCat (QQ Client)
      │  WebSocket
      ▼
WebSocketClient (singleton, message queue)
      │
      ▼
message_router.main()
      │
      ├──► EventTrigger       (keywords/poke/member change events)
      ├──► CommandSystem       (@bot /cmd commands)
      └──► LLMCoordinator      (LLM chat main pipeline)
```

The bot is purpose-built for chat. Only essential message processing is needed—no plugin system or unnecessary complexity. Messages are simply filtered into @-mentions (commands vs. chat) and others (dispatched to EventTrigger).

---

### 🧠 LLM Chat Pipeline

The core LLM chat pipeline resides in `atribot/LLMchat/` and follows a **fully asynchronous pipeline** design:

```
User Message (ChatMessage)
      │
      ▼
chat.py → GroupChat.step()          ← Chat entry point
      │
      ├─① prompt_structure()        Build prompt
      │     ├─ Group chat history (recent message window)
      │     ├─ User profile (UserSystem)
      │     ├─ Recent memory snippets (memorySystem.query_user_recently_memory)
      │     ├─ Emoji prompts (EmojiCore)
      │     └─ Skills prompts (SkillsManager)
      │
      ├─② LLMCoordinator.run()      Dispatch model request
      │     ├─ Primary model request (model_api)
      │     ├─ Function Calling loop (MCP/tools)
      │     └─ Fallback to standby models on failure (_request_model_with_fallback_)
      │
      ├─③ Parse JSON response       Model outputs structured decisions
      │     ├─ "reply"    → Send response (segmented / with emojis)
      │     ├─ "update"   → Update user profile
      │     ├─ "silence"  → No reply
      │     └─ "use_tools"→ Invoke tools
      │
      └─④ Post-processing
            ├─ Context write-back (ChatManager)
            └─ Trigger summarize_context() when context exceeds token limit
```

**High-Availability Fallback**: When the primary model API returns an error, `_request_model_with_fallback_` iterates through `config.model.standby_model` list to try backup providers and models, ensuring responses even when the primary key fails.

**Structured Output**: The model is instructed to return JSON-formatted decision lists (with a `return` array), each item containing a `decision` field, making response behavior fully controllable and extensible.

---

### 💾 Memory System Design

The memory system consists of two layers: **short-term context cache** and **long-term vector memory**.

#### Short-term Context (ChatManager)
- Each group/user maintains a sliding message window `Context`, directly embedded into each request's `messages` list.
- When the context exceeds the token limit, `memorySystem.summarize_context()` triggers LLM-based compression of older messages. The compressed summary is inserted as an `assistant` role message at the head of the context.

#### Long-term Vector Memory (memorySystem + pgvector)

```
After chat ends
      │
      ▼
memorySystem.extract_stored_group_message()
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

**Hybrid Recall**: A single CTE-based SQL query performs both **vector retrieval** (pgvector cosine distance) and **full-text retrieval** (pgroonga), then fuses results via RRF (Reciprocal Rank Fusion), with final ranking by importance, access frequency, and time decay.

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
- **Background Defragmentation**: A scheduled maintenance task clusters recently active, highly similar memories using connected graph analysis, then safely merges and deduplicates them via LLM, preventing redundant information buildup.
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
