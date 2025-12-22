<img src=".\assets\ATRI-bot.png" width = "400" height = "400" alt="ATRI-bot" align=right />
<div align="center">

# ATRI-bot

>_时间流逝吧，你是多么的残酷；时间停止吧，你是多么的美丽_
>
> — *ATRI -My Dear Moments-*

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![NapCat](https://img.shields.io/badge/Backend-NapCat-green.svg)](https://github.com/NapNeko/NapCatQQ)

</div>

## 📖 前言

来自萌新到处学习(抄袭，不对是集百家之长 ✨)做出来私用的神秘项目.
主要是**按照自己的需求**编写一个专到狭窄的学习性质的项目(专注于提供一个深度定制化的群聊机器人体验),发出来是用来交流学习的.
项目名称致敬了一个游戏，希望这个 Bot 能像亚托莉一样成为你珍贵的伙伴(虽然现在还不是很完善)

---

## ✨ 项目核心功能

简单来说，这是一个基于 **NapCat** 对接的、专注于群聊场景的 QQ Bot。除了群聊以外的其他的功能都没没做

### 🧠 深度 LLM 聊天集成
完全自主实现的 LLM 聊天全流程，从输入处理到输出响应完全可控：
- **全异步高并发**：回复流程完全异步，支持 Key 号池轮询，面对多个群聊的高并发场景也能轻松应对。
- **自主可控**：支持函数调用（Function Calling）及 **MCP (Model Context Protocol)** 配置。
- **RAG 记忆系统**：基于 RAG（检索增强生成）实现的记忆功能，支持知识库问答，让 Bot 拥有“长期记忆”。
- **高可用设计**：设计了备用 API 响应机制。当主模型响应错误时，会自动降级到配置的其他模型（虽然速度可能稍慢，但保证有问必达）。
- **拟人化交互**：
  - 支持自然地发送表情包。
  - 模拟人类说话习惯，支持分段发送消息。
  - **主动话题参与**：达到一定条件时，会尝试主动回复群消息，融入话题。
  - **用户画像维护**：维护 User 文档用于嵌入上下文，保证对同一用户的态度一致性。
  - 支持人设切换等基础功能。

### 💻 类 Unix 命令系统
拥有一套可用的命令机制，在群里 `@bot` 后以 `/` 开头即可触发（例如 `@atri-bot /help --list`一定要是qq的那个@而不是@+名字文本）：
- **参数解析**：支持 `-` 和 `--` 等参数风格，内置参数类型验证。
- **权限管理**：内置权限系统，支持拉黑或授予管理员权限。可在任意处理环节校验 User 权限，拒绝非法执行。
- **自动帮助文档**：只要在代码中使用装饰器并添加参数说明，即可自动生成详细的 `--help` 提示。

### 🛠️ 其他实用功能
- **高性能关键词匹配**：配置文件支持关键词响应，底层采用 **AC 自动机** 算法，即使配置上万条匹配项也能保持毫秒级响应。
- **群成员变动提醒**：有人加入或退出群聊时自动通知。
- **戳一戳互动**：被戳时会有反应，甚至会“戳回去”。
- **强健的架构**：数据库采用连接池，消息接收引入消息队列机制，抗压能力 Max。

---

## 🚀 快速开始 (How to Run)

### 1. 前端连接 (NapCat)
首先需要一个能够与 QQ 服务器通信的前端，推荐使用 NapCat连接QQ：
[NapCat 安装指南](https://napneko.github.io/guide/napcat)
[NapCat 项目地址](https://github.com/NapNeko/NapCatQQ)
> *注：你也可以自己实现前端，只要能对接上即可。*

### 2. 数据库配置 (PostgreSQL)
项目仅支持 PostgreSQL 数据库。
1.  **安装数据库**：推荐使用 PostgreSQL 18 或更高版本。[官方安装文档](https://www.postgresql.org/download/)
2.  **安装向量插件**：必须安装 `pgvector` 插件以支持 RAG 功能.[pg向量插件](https://github.com/pgvector/pgvector)
3.  **数据库初始化**：
    项目提供了初始化 SQL 文件：`docker\db\info.sql`。
    进入数据库（Linux 示例）：
    ```bash
    sudo -u postgres psql
    ```
    然后按顺序执行 `info.sql` 中的内容创建表结构。


### 3. 模型与环境配置
#### 🤖 嵌入模型 (Embedding)
推荐使用本地的 `Qwen3-Embedding-0.6B:F16`当然你有其他付费 API 也可以。(不知道其他渠道是否能使用,只测试过ollama)
推荐使用 [Ollama](https://ollama.com/) 进行本地部署：
```bash
ollama run Qwen3-Embedding-0.6B:F16
```

> **注意**：如果更换 Embedding 模型，之前构建的向量数据需要重新构建。


#### 🗣️ 语音合成 (TTS) - 可选
支持接入 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)
实现 Bot 主动发送语音或通过命令调用语音功能，可以设置语速情感等常用参数
然后再修改`atribot\commands\audio\TTS.py`文件里的参考音频路径,还有GPT-SoVITS接口的端口地址
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


#### ⚙️ 配置文件
在启动前，请务必检查 `assets` 文件夹：
1.  参考 `assets\如何配置配置文件.py` 了解配置详情。
2.  配置 `supplier_config.json` (模型供应商配置)。
3.  配置 `config.json` (项目基础配置)。
4.  **MCP 配置**：默认路径在 `atribot\LLMchat\MCP\mcp_server.json`，可通过 `"active": false` 开关特定的 MCP 工具。
5.  根目录`document/`下面可参照项目结构添加对应的音频表情包文件配置

### 4. 启动项目
项目依赖 **Python 3.13** 环境。推荐使用 `uv` 进行包管理。

**使用 uv (推荐):**
```bash
# 进入项目根目录
uv sync
uv run main.py
```

**使用 pip:**
```bash
pip install -r requirements.txt
python3 main.py
```
> ⚠️ **重要**：执行命令时请务必保持在项目根目录下，否则可能会出现路径错误。

---
## 📂 项目结构

```text
ATRI-main/
├─assets/                       # ⚙️ 项目配置文件及配置说明
│
├─atribot/                      # 核心代码实现
│  ├─C/                         # C语言扩展模块 (编译成链接库以提升性能)
│  ├─commands/                  # 💻 命令具体实现逻辑
│  ├─core/                      # 核心架构
│  │  ├─cache/                  # 内存消息缓存
│  │  ├─command/                # 命令系统与权限系统实现
│  │  ├─db/                     # 数据库连接池实现
│  │  ├─event_trigger/          # 基础消息事件处理
│  │  └─network_connections/    # 网络连接与消息收发
│  │
│  ├─docs/                      # 开发笔记与文档
│  │
│  ├─LLMchat/                   # 🧠 聊天模块实现
│  │  ├─character_setting/      # 人设预设
│  │  ├─discard_tools/          # (已废弃的工具)
│  │  ├─MCP/                    # MCP 协议工具与配置
│  │  ├─memory/                 # RAG 记忆系统
│  │  ├─model_api/              # LLM 供应商连接接口
│  │  ├─RAG/                    # 检索增强生成逻辑
│  │  └─tools/                  # 函数调用工具集
│  │
│  └─log/                       # 运行时日志配置
│
├─docker/                       # 🐳 Docker 部署相关 (WIP)
│  ├─db/                        # 数据库初始化 SQL
│  └─python/
│
├─document/                     # 🎨 资源文件夹
│  ├─audio/                     # 音频素材
│  ├─file/                      # 通用文件
│  ├─img/                       # 图片素材
│  │  └─emojis/                 # Bot 发送的表情包文件夹
│  │     ├─RocketPunch          # Bot 发送的表情包对应的分类表情可添加配置多个文件夹
│  │     └─happy
│  └─video/                     # 视频素材
```

---

## 🤝 参与贡献

非常欢迎你参与到这个项目中来！无论是提交 Bug、修补代码还是提出新功能建议。
让我们一起把 ATRI 变得更聪明、更可爱！
虽然这个目前其实很烂

---
<div align="center">
❤️ ATRI-bot ❤️
</div>