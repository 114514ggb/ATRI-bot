````instructions
# ATRI-bot AI Coding Instructions

## Architecture Overview
- **Entry Point**: `main.py` → `atribot/bot_framework.py`（`BotFramework.create()` 工厂方法）。所有服务在 `initialize()` 中**严格按顺序**注册，初始化完成后调用 `TimeTriggerSupervisor.start()` 启动定时循环。
- **实际初始化流程**:
  1. 注册 `config`（atriConfig）
  2. `_register_services()` — 批量将类注册到 `DIContainer`
  3. `_register_network()` — 根据 `connection_type` 注册 `WebSocketClient` 或 `WebSocketServer`
  4. `_start_sandbox()` — **在服务解析之前**启动 Docker 沙盒（可选，失败不阻断）
  5. `_resolve_services()` — 按以下 `_RESOLVE_TARGETS` 顺序解析（实例化 + 依赖注入 + `initialize()`）：
     `HTTPClient` → `TimeTriggerSupervisor` → `MCP`(FuncCall) → `database`(AsyncPostgreSQL) → `TokenManager` → `LLMSupplier`(LLMConnectionManager) → `SkillsManager` → `memorySystem` → `UserSystem` → `ChatManager` → `EmojiCore` → `PermissionsManagement` → `SendMessage`(QQAPIClient) → `EventTrigger` → `CommandSystem` → `ToolCalls`(tool_calls) → `MediaProcessor` → `LLMSupervisor`(LLMCoordinator) → `GroupChat` → `PrivateChat`
  6. 在 `_resolve_services` 最后，手动注册 `command_loader`（`CommandLoader`）
  7. `_start_runtime_services()` — 启动 `TimeTriggerSupervisor` 循环及 `admin_panel`
  8. `_start_network()` — 绑定 `message_router` 并开始监听
- **依赖注入**: 使用单例 `DIContainer`（`atribot/core/service_container.py`）。核心 API：
  - `container.get("ServiceName")` — 获取已解析实例
  - `container.get_by_type(ClassName)` — 按类型获取实例
  - `container.register(name, obj, cleanup=None)` — 注册实例（可附带清理回调）
  - `container.register_class(cls, name=None)` — 注册类供后续 `resolve()` 解析
  - `container.register_factory(cls, factory, name=None)` — 使用工厂函数注册
  - `container.resolve(cls)` — **最核心方法**：自动解析构造参数（从容器注入）、实例化、调用 `initialize()`（若存在）、注册 `cleanup` 回调（若存在）
  - `container.register_cleanup(name, handler)` — 单独注册清理回调
  - `container.exists(name)` — 检查服务是否存在
  - `container.shutdown()` — 按**注册逆序**执行所有 cleanup 回调
- **消息流**: `NapCat`（外部QQ） → `WebSocketClient`（单例） → `message_router.main()` → 群聊白名单校验 → `PermissionsManagement.check_access()` → `CommandSystem` 或 `EventTrigger` 或 `LLMCoordinator`。群聊由 `GroupChat` 处理，私聊由 `PrivateChat` 处理。
- **数据库**: PostgreSQL + `pgvector`（HNSW 1024维，m=16/ef=64）+ `pgroonga` 扩展。全异步，使用 `async with db as db:` 上下文管理器。Schema 定义在 `docker/db/info.sql`，含自定义枚举 `permission_type`、`memory_category`。
- **配置访问**: `atriConfig` 将 JSON 包装为支持点操作的 `ConfigObject`（`assets/config.json`）。路径统一通过 `config.file_path.*` 访问，均为 `Path` 对象。

## 完整服务名称表
| 服务名 | 类型 | Shutdown | 备注 |
|---|---|---|---|
| `log` | `Logger` | — | 容器初始化时自动注册 |
| `config` | `atriConfig` | — | |
| `HTTPClient` | `HTTPClient` | — | 异步 HTTP 客户端（`get_bytes`/`post_form`/`post_json`） |
| `database` | `AsyncPostgreSQL` | ✅ `close_pool()` | 需 `async with` 使用 |
| `TokenManager` | `TokenManager` | — | Token 用量统计 |
| `SendMessage` | `QQAPIClient` | — | QQ 消息发送 API |
| `LLMSupplier` | `LLMConnectionManager` | ✅ `close()` | LLM 供应商连接管理 |
| `LLMSupervisor` | `LLMCoordinator` | — | LLM 调度协调 |
| `CommandSystem` | `CommandSystem` | — | 命令注册与解析 |
| `memorySystem` | `memorySystem` | — | 记忆系统门面（聚合 Retriever/Extractor/Consolidator） |
| `SandBox` | `DockerSandbox` | ✅ `stop()` | 初始化可能失败，使用前调用 `container.exists("SandBox")` |
| `SkillsManager` | `SkillsManager` | — | Agent Skills 加载与管理 |
| `MCP` | `FuncCall` | ✅ `terminate()` | MCP 通过后台队列异步初始化 |
| `TimeTriggerSupervisor` | `TimeTriggerSupervisor` | ✅ `stop()` | 定时任务调度 |
| `UserSystem` | `UserSystem` | — | 用户信息管理 |
| `ChatManager` | `ChatManager` | — | 群聊/私聊上下文管理 |
| `EmojiCore` | `EmojiCore` | — | 表情系统 |
| `PermissionsManagement` | `PermissionsManagement` | — | async 创建，权限 0-3 四级 |
| `EventTrigger` | `EventTrigger` | — | 事件钩子注册与分发 |
| `WebSocket` | `WebSocketServer` 或 `WebSocketClient` | ✅ `close()` | 由 `connection_type` 决定 |
| `ToolCalls` | `tool_calls` | ✅ cleanup | 本地工具加载与预设管理 |
| `MediaProcessor` | `MediaProcessor` | — | 多模态转文本（image/audio/video → text） |
| `GroupChat` | `GroupChat` | — | 群聊 LLM 对话处理 |
| `PrivateChat` | `PrivateChat` | — | 私聊 LLM 对话处理 |

## 消息类型系统

### ChatMessage 对象
处理函数的**第一个参数固定为** `message_data: ChatMessage`（`atribot/core/type/chat_message_types.py`）：
```python
@dataclass
class ChatMessage:
    self_id: int              # 接收账号 QQ
    user_id: int | None       # 发送者 QQ
    group_id: int | None      # None = 私聊
    message_id: int           # 消息唯一 ID
    time: int                 # Unix 时间戳
    raw_message: str          # 原始 CQ 码文本
    user_cq_message: str      # 精简版 CQ 码文本
    primeval: dict            # 原始事件完整字典
    llm_formatted_message: str = ""  # AI 可读格式化消息（默认空，需调用 update_llm_formatted_message() 更新）
    pure_text: str = ""       # 提取的纯文本内容
    segments: List[MessageSegment] = field(default_factory=list)  # 结构化消息段列表
    sender_info: Dict[str, Any] = field(default_factory=dict)    # 发送者信息：{'user_id', 'nickname', 'card', 'role'}
    
    def update_llm_formatted_message(self) -> None  # 调用 format_for_llm() 更新 llm_formatted_message 字段
```

> **注意**：`sender_nickname` 不是独立字段，通过 `message_data.sender_info["nickname"]` 访问。

### MessageSegment 消息段类型
| 类名 | 用途 | 构造 |
|---|---|---|
| `TextSegment` | 纯文本 | `TextSegment(text)` |
| `MarkdownSegment` | Markdown 文本 | `MarkdownSegment(text)` |
| `XmlSegment` | XML 消息 | `XmlSegment(text)` |
| `ImageSegment` | 图片 | `ImageSegment(file: File, file_name=None, url=None, summary=None)` |
| `AtSegment` | @用户 | `AtSegment(user_id)` |
| `ReplySegment` | 回复消息 | `ReplySegment(message_id)` |
| `RecordSegment` | 语音 | `RecordSegment(file: File, file_name=None, url=None)` |
| `VideoSegment` | 视频 | `VideoSegment(file: File, file_name=None, url=None, thumb=None)` |
| `FaceSegment` | QQ 表情 | `FaceSegment(face_id)` |
| `ForwardSegment` | 合并转发 | `ForwardSegment(id, content=None)` |
| `JsonSegment` | JSON 卡片 | `JsonSegment(json_data: dict \| str)` |
| `FileSegment` | 文件 | `FileSegment(file: File, file_name=None)` |
| `NodeSegment` | 转发节点 | `NodeSegment(content: list, nickname="ATRI-亚托莉", ...)` |
| `UnknownSegment` | 未适配类型 | `UnknownSegment(type_str, data)` |

### File 封装类
`File` 是一个 `@dataclass`（`chat_message_types.py`），用于封装文件路径：
```python
@dataclass
class File:
    file: str  # 支持 file://、http(s)://、base64:// 协议前缀
```

### SendMessage（多模态消息构建）
> **注意**：此处的 `SendMessage` 是多模态消息构建器类（位于 `atribot/core/type/chat_message_types.py`），与发送服务 `QQAPIClient`（也注册为 `SendMessage`）不同。

```python
from atribot.core.type.chat_message_types import SendMessage

msg = (SendMessage()
    .add_text("说明文字")
    .add_image("https://...")
    .add_at(123456789)
    .add_reply(987654321)
    .add_markdown("**粗体**")
    .build())   # data 属性 → List[Dict[str, Any]]（OneBot 标准格式）
```

**完整方法列表**（均返回 `self` 支持链式调用）：
| 方法 | 说明 |
|---|---|
| `add_text(text: str)` | 添加纯文本 |
| `add_markdown(text: str)` | 添加 Markdown 文本 |
| `add_xml(text: str)` | 添加 XML 消息 |
| `add_image(file, file_name=None, summary=None)` | 添加图片（file 可为 `str` 或 `File`） |
| `add_at(user_id: int)` | @用户 |
| `add_reply(message_id)` | 回复消息 |
| `add_face(face_id)` | QQ 表情 |
| `add_record(file, file_name=None)` | 添加语音 |
| `add_video(file, file_name=None, thumb=None)` | 添加视频 |
| `add_file(file, file_name=None)` | 添加文件 |
| `add_json(json_data: str)` | 添加 JSON 卡片 |
| `add_forward(id, content=None)` | 合并转发 |
| `add_node(content, nickname="ATRI-亚托莉", ...)` | 转发节点 |
| `add_segment(segment: MessageSegment)` | 添加自定义消息段 |
| `clear()` | 清空消息 |
| `data` (属性) | 返回 `List[Dict[str, Any]]` |
| `to_json()` | 返回 JSON 字符串 |

## 权限体系
`PermissionsManagement`（`AsyncPermissionsManagement`）四级权限：
- `0`：黑名单（被封禁）
- `1`：普通用户（默认）
- `2`：管理员
- `3`：Root 用户

`authority_level` 字段含义：`0`=无限制，`1`=普通用户可用，`2`=管理员，`3`=Root。

## Key Extension Patterns

### 1. 添加新命令
- 在 `atribot/commands/<category>/` 下创建目录，`command_loader`（`CommandLoader`）自动扫描并加载各子目录的 `__init__.py`。
- **重要**：`command_loader` 动态注入父模块时必须设置 `__path__`，否则子模块绝对导入会报"不是包"。加载命令包时应先执行 `__init__.py`，再加载同级其他 `.py` 文件，避免同包绝对导入失败。
- 处理函数**第一个参数固定为** `message_data: ChatMessage`，通过 `message_data.group_id`、`message_data.user_id` 等属性访问。
- **三种参数装饰器**（顺序：register_command → option/argument/flag → 处理函数）：

```python
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

cmd_system = container.get("CommandSystem")
send_message = container.get("SendMessage")

@cmd_system.register_command(
    name="cmd",
    description="命令描述",
    authority_level=1,
    aliases=["别名"],
    examples=["/cmd arg --opt value"]
)
# 位置参数（/cmd value）
@cmd_system.argument(name="param", description="...", required=True, type=str, multiple=False)
# 选项参数（--opt value 或 -o value）
@cmd_system.option(name="opt", short="o", long="--opt", description="...", required=False, default=None, type=str)
# 布尔标志（--flag 或 -f，无值）
@cmd_system.flag(name="verbose", short="v", long="--verbose", description="详细输出")
async def handler(message_data: ChatMessage, param: str, opt: str | None, verbose: bool) -> None:
    await send_message.send_group_msg(message_data.group_id, f"Response: {param}")
```

### 2. LLM Function Calling 工具
- 在 `atribot/LLMchat/tools/<tool_name>/` 下创建目录 + `__init__.py`。
- 必须导出：`tool_json`（OpenAI function calling 格式）和 `async def main(**kwargs)` 执行函数。

```python
tool_json = {
    "name": "unique_tool_name",
    "description": "工具说明",
    "properties": {
        "param": {"type": "string", "description": "参数说明", "enum": ["a", "b"]},
        "count": {"type": "number", "description": "数量", "minimum": 1, "maximum": 100}
    }
}

async def main(**kwargs) -> Any:
    param = kwargs.get("param")
    # kwargs key 与 tool_json.properties 一致
```

**已内置工具**：`web_search`、`web_extract`、`get_user_info`、`memory_search`、`send_image_message`、`send_speech_message`、`send_create_image`、`load_skill_prompt`、`run_python_code`（沙盒执行）。

### 3. 定时任务
- 通过 `container.get("TimeTriggerSupervisor")` 获取调度器，支持一次性、固定间隔、Cron 三种模式：
  ```python
  trigger = container.get("TimeTriggerSupervisor")
  await trigger.add_task(func=my_async_func, interval=60.0, remarks="每分钟")
  await trigger.add_task(func=my_func, cron_expression="0 9 * * *", remarks="每天9点")
  ```

### 4. Agent Skills
- 在 `atribot/LLMchat/skills/agent_skills/<skill-name>/` 下创建含 YAML frontmatter 的 `SKILL.md`。
- 必填字段：`name`（小写字母+数字+`-`）和 `description`；可选：`version`、`author`、`tags`。
- 参考说明文档：`atribot/LLMchat/skills/agent_skills/如何创建一个skills.md`。
- 技能在运行时通过 `load_skill_prompt` 工具加载给 LLM 使用，也可通过 `container.get("SkillsManager").get_skill_md_prompt(skill_name)` 直接获取。
- **性能说明**：`SkillsManager` 启动时使用 `validator.load_validated_properties()` 一次性完成读取、解析、验证和 `SkillProperties` 构建，避免重复 I/O。

### 5. EventTrigger 扩展
- 使用装饰器注册钩子，支持带条件 lambda 过滤。处理函数若返回 `True` 则**拦截后续处理**，不再向下分发。
  ```python
  event_trigger = container.get("EventTrigger")
  
  @event_trigger.on_message(condition=lambda data: "关键词" in data.get("raw_message", ""))
  async def handler(message: ChatMessage, data: dict) -> bool:
      # 返回 True 拦截后续处理
      return False
  
  @event_trigger.on_notice(lambda data: data.get("sub_type") == "poke")
  async def on_poke(message: ChatMessage, data: dict) -> None:
      pass
  
  @event_trigger.on_request(lambda data: data.get("sub_type") == "add")
  async def on_add_group(message: ChatMessage, data: dict) -> None:
      pass
  
  @event_trigger.on_meta(lambda data: data.get("meta_event_type") == "heartbeat")
  async def on_heartbeat(message: ChatMessage, data: dict) -> None:
      pass
  
  @event_trigger.on_message_sent(lambda data: True)
  async def on_self_message(message: ChatMessage, data: dict) -> None:
      pass
  ```
- 也可使用通用 `on(event_type, condition)` 装饰器，`event_type` 取自 `EventType` 枚举。
- 也可以直接在 `atribot/core/event_trigger/event_trigger.py` 的 `processors` 列表中添加 `(条件lambda, 处理协程)` 元组。

## SendMessage API（QQAPIClient）
```python
send_message = container.get("SendMessage")

await send_message.send_group_msg(group_id, message)        # 发送文本
await send_message.send_group_message(group_id, message)    # 同上
await send_message.send_group_reply_msg(group_id, message, reply_message_id)  # 快捷回复
await send_message.send_group_audio(group_id, url_audio)    # 发送语音
await send_message.send_group_video(group_id, url_video)    # 发送视频
await send_message.send_group_pictures(group_id, url_img, local_Path_type=False)  # 发送图片
await send_message.send_group_file(group_id, url_file, local_Path_type=True)      # 发送文件
await send_message.send_group_merge_text(group_id, message, source="来源")        # 合并转发（单条文本）
await send_message.send_group_merge_forward(group_id, input_messages, ...)        # 多节点合并转发
await send_message.get_group_info(group_id)                 # 获取群信息
await send_message.get_msg_details(message_id)              # 获取消息详情
await send_message.set_group_add_request(flag, approved)    # 处理加群申请
await send_message.set_group_ban(group_id, user_id, duration)  # 禁言
await send_message.set_msg_emoji_like(message_id, emoji_id, set)  # 消息贴表情
```
URL 格式：`http(s)://...`、`file://绝对路径`（需 `local_Path_type=True`）、`base64://编码字符串`。

## 记忆系统
- `memorySystem` 是门面类（`atribot/LLMchat/memory/memory_system.py`），内部聚合 `MemoryRetriever`（向量+全文检索）、`MemoryExtractor`（LLM 提取记忆）和 `MemoryConsolidator`（记忆合并去重）。**关键实践**：构建时应共享 `MemoryRetriever`/`MemoryExtractor` 实例注入 `MemoryConsolidator`，避免重复初始化 LLM 供应商和模型。相似度边 SQL 聚集逻辑归属 `MemoryRetriever`，`MemoryConsolidator` 仅负责编排聚集/合并流程。
**MemoryCategory** 8 种分类（`atribot/LLMchat/memory/vector_store.py`）：
```
"preference"  # 用户偏好
"fact"        # 事实性记忆（默认）
"experience"  # 经历记忆
"emotion"     # 情感记忆
"group_topic" # 群聊话题/群体共识
"knowledge"   # 通用知识条目
"domain"      # 领域专业知识
"guideline"   # 行为准则知识
```

`group_id` 语义：`None` = 知识库，`0` = 私聊，`>0` = 群聊。记忆条目含 `importance`（1-10）和 `credibility`（1-10）质量指标，HNSW 向量索引 + pgroonga 全文索引双重检索。

## 数据库 API（AsyncPostgreSQL）
```python
db = container.get("database")
async with db as db:
    rows = await db.fetch(sql, params)
    row  = await db.fetchrow(sql, params)
    await db.execute(sql, params)
    # 内置便捷方法
    await db.add_user(user_id, nickname)
    await db.add_message(message_id, content, ...)
    await db.add_group(group_id, group_name)
```
核心表：`users`、`user_group`、`user_info`、`permissions`、`message`、`atri_memory`（pgvector 1024维）、`chat_context`（JSONB 上下文）。

## Coding Standards
- **异步优先**: 所有 IO（DB、网络、LLM API）必须使用 `async/await`。
- **绝对路径**: 使用 `container.get("config").file_path.*` 获取路径，**禁止使用相对路径**。
  - 项目路径：`project_root`、`document_root`
  - 核心目录：`commands`、`chat_manager`、`supplier_config_path`、`agent_skills`、`tool_calls`、`mcp_config`
  - 文档目录：`emoji`、`audio`、`img`、`video`、`temp`、`file`
- **日志**: `log = container.get("log")`，使用 `log.info/warning/error/exception()`。
- **类型注解**: 所有函数参数和返回值都需添加类型注解。
- **优雅关闭**: 新服务注册后，调用 `container.register_cleanup(name, cleanup_coro)` 注册清理回调（shutdown 按逆序执行）。

## Critical Developer Workflows
- **运行 Bot**: 从**项目根目录**执行 `uv run main.py` 或 `python main.py`，路径解析依赖工作目录。
- **数据库 Schema**: 修改持久化逻辑前先查看 `docker/db/info.sql`，所有新建表应在此文件定义。
- **LLM 供应商配置**: 在 `assets/supplier_config.json` 中添加供应商（`base_url` + `api_key` + `model_dict`）。智谱AI（`bigModel`）在 `bot_framework.py` 中硬编码注册，支持 GLM-4.5/4.6V/4.1V 等系列。
- **备用模型**: `config.model.standby_model` 列表维护多个备选模型，主模型不可用时自动切换。
- **RAG/Memory**: 记忆系统基于 pgvector 向量检索（Qwen3-Embedding 1024维 + Qwen3-Reranker 重排序），入口为 `container.get("memorySystem")`，向量分类参见 MemoryCategory 8 种枚举。
- **MCP 服务**: 配置文件路径由 `config.file_path.mcp_config` 指定（`atribot/LLMchat/MCP/mcp_server.json`），支持 SSE 和 Streamable HTTP。`FuncCall` 通过 `asyncio.create_task` 启动后台 `mcp_service_selector`，使用 `asyncio.Queue` (`mcp_service_queue`) 管理指令：`{"type": "init"}` 初始化所有激活服务，`{"type": "terminate"}` 关闭所有服务；`active: false` 的服务不会启动。配置格式：
  ```json
  {
    "mcpServers": {
      "server_name": {
        "command": "uvx",
        "args": ["..."],
        "env": {"KEY": "VALUE"},
        "active": true,
        "type": "sse", "url": "http://..."
      }
    }
  }
  ```
- **SandBox**: 使用前务必调用 `container.exists("SandBox")` 检查，`DockerSandbox` 初始化失败不阻断启动；沙盒镜像预装 numpy/pandas/matplotlib/pillow/opencv。
- **群组白名单**: `config.group_white_list` 控制哪些群接收消息处理，`group_initiative_chat_white_list` 控制主动发起对话的群，`group_information_extraction` 指定自动提取话题的群。

````