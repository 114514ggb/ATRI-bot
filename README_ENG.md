<img src="./assets/ATRI-bot.png" width="400" height="400" alt="ATRI-bot" align="right" />
<div align="center">

# ATRI-bot

> _時よ止まれ、おまえは美しい_  
>
> — *ATRI -My Dear Moments-*

Project logo drawn by [吖密](https://space.bilibili.com/1196260828)

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED.svg)](https://www.docker.com/)
[![NapCat](https://img.shields.io/badge/Backend-NapCat-green.svg)](https://github.com/NapNeko/NapCatQQ)

</div>

## 📖 Introduction

A personal hobby project created by a beginner learning (or rather, "combining the strengths of many" ✨) from various sources.  
It is primarily a **highly customized** learning-oriented project (focused on providing a deeply tailored group chat bot experience), shared here for exchange and learning purposes.  
The project name pays tribute to a game, hoping this bot can become your precious companion like Atori (though it's still a work in progress).

---

## ✨ Core Features

In short, this is a **NapCat**-connected QQ Bot focused on group chat scenarios. Other features outside of group chat are not implemented.

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

---

## 🚀 Quick Start (How to Run)

### 1. Frontend Connection (NapCat)
First, you need a frontend that can communicate with the QQ server. NapCat is recommended:  
[NapCat Installation Guide](https://napneko.github.io/guide/napcat)  
[NapCat Repository](https://github.com/NapNeko/NapCatQQ)
> *Note: You can also implement your own frontend, as long as it can connect properly.*

### 2. Database Configuration (PostgreSQL)
The project only supports PostgreSQL.
1.  **Install PostgreSQL**: Recommended version 18 or higher. [Official Installation Docs](https://www.postgresql.org/download/)
2.  **Install vector extension**: Must install the `pgvector` extension for RAG functionality. [pgvector Extension](https://github.com/pgvector/pgvector)
3.  **Database initialization**:
    The project provides an initialization SQL file: `docker/db/info.sql`.  
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
Before use, modify `atribot/commands/audio/TTS.py `to set the reference audio path and GPT-SoVITS API port address:
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

- **Extensibility**： To support other sandbox types (e.g., web sandbox, system command sandbox), inherit from the base class in `atribot/LLMchat/sandbox/sandbox_base.py` and implement the corresponding interface.
- **Enable/Disable**：Sandbox is **enabled** by default. If Docker is not installed or configured in the runtime environment, project initialization will fail. To disable, locate the code marked with `# ai使用的沙盒` in `atribot/bot_framework.py` and comment it out.

#### ⚙️ Configuration Files
Before starting, ensure to check the  `assets` folder:
1.  Refer to `assets\如何配置配置文件.py` (Chinese guide) for configuration details.
2.  Configure `supplier_config.json` (model supplier settings).
3.  Configure `config.json` (project basic settings).
4.  **MCP Configuration**：Default path is `atribot\LLMchat\MCP\mcp_server.json`. Specific MCP tools can be toggled via `"active": false`.
5.  Under root `document/`, you can add corresponding audio, emoji, and file configurations according to the project structure.
### 4. Start the Project
The project requires **Python 3.13**. Using `uv` for package management is recommended.

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

---
## 📂 Project Structure

```text
ATRI-main/
├─assets/                       # ⚙️ Project configuration files & guides
│
├─atribot/                      # Core code implementation
│  ├─C/                         # C extension modules (compiled to libraries for performance)
│  ├─commands/                  # 💻 Command implementation logic
│  ├─core/                      # Core architecture
│  │  ├─cache/                  # In-message caching
│  │  ├─command/                # Command system & permission system
│  │  ├─db/                     # Database connection pool
│  │  ├─event_trigger/          # Basic message event handling
│  │  └─network_connections/    # Network connections & message I/O
│  │
│  ├─docs/                      # Development notes & documentation
│  │
│  ├─LLMchat/                   # 🧠 Chat module implementation
│  │  ├─character_setting/      # Character presets
│  │  ├─discard_tools/          # (Deprecated tools)
│  │  ├─MCP/                    # MCP protocol tools & configuration
│  │  ├─memory/                 # RAG memory system
│  │  ├─sandbox/                # Sandbox for AI code execution
│  │  ├─model_api/              # LLM supplier connection interfaces
│  │  ├─RAG/                    # Retrieval-Augmented Generation logic
│  │  └─tools/                  # Function calling toolset
│  │
│  └─log/                       # Runtime log configuration
│
├─docker/                       # 🐳 Docker deployment (WIP)
│  ├─db/                        # Database initialization SQL
│  └─python/
│
├─document/                     # 🎨 Resource folder
│  ├─audio/                     # Audio assets
│  ├─file/                      # Generic files
│  ├─img/                       # Image assets
│  │  └─emojis/                 # Emojis/stickers sent by the bot
│  │     ├─RocketPunch          # Categories for bot emojis (can add multiple folders)
│  │     └─happy
│  └─video/                     # Video assets
```

---

## 🤝  Contributing

You are very welcome to contribute to this project! Whether it's reporting bugs, fixing code, or suggesting new features.
Let's make ATRI smarter and cuter together!
(Though it’s still quite rough at the moment.)

---
<div align="center">
_私は、高性能ですから!_

<img src="https://files.astrbot.app/watashiwa-koseino-desukara.gif" width="100"/>

❤️ ATRI-bot ❤️
</div>
<div align="right">
[English Version](README_ENG.md) | [中文版本](README.md)
</div>
