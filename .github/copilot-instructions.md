````instructions
# ATRI-bot AI Coding Instructions

## Architecture Overview
- **Entry Point**: `main.py` → `atribot/bot_framework.py`（`BotFramework.create()` 工厂方法）；服务在 `initialize()` 中**严格按顺序**注册/解析，初始化完成后依次执行 `_platform_manager.start_all()` 与 `_start_runtime_services()`（启动定时循环 + Web 管理面板后台任务）
- **实际初始化流程**（`BotFramework.initialize()`，见 `atribot/bot_framework.py`）:
  1. 注册 `config`（atriConfig 实例）
  2. `_register_services()` — 分两组注册：`_SERVICE_CLASSES`（类名即服务名，含 `CommandLoader`、`PluginManager`、`MessageSender`）和 `_NAMED_SERVICE_CLASSES`（显式指定服务名的类：`AsyncPostgreSQL`→`"database"`、`ToolManager`→`"MCP"`、`LLMConnectionManager`→`"LLMSupplier"`、`ToolCalls`→`"ToolCalls"`）
  3. 创建 `PlatformManager`（`atribot/core/platform/manager.py`）并注册（cleanup=`stop_all`，另手动补写 `_type_map`）；发送能力入口统一走 `PlatformManager` / `atriMessageEvent.send_client`，**不再注册 `SendMessage` 服务**（旧桥接 `container.register("SendMessage", ...)` 已移除），无适配器时仅 warning
  4. `_start_sandbox()` — **在服务解析之前**启动沙盒（可选，失败不阻断）：由 `sand_box.type` 选择后端 `docker`（默认）/ `none|no_sandbox|local`（本机直执行）/ `e2b`，统一经 `sandbox/factory.py` 构建，成功后注册容器服务 `"SandBox"`（cleanup=`stop`）
  5. `_resolve_services()` — 按以下 `_RESOLVE_TARGETS` 顺序解析（实例化 + 依赖注入 + `initialize()`），共 21 项：
     `HTTPClient` → `TimeTriggerSupervisor` → `MCP`(ToolManager) → `database`(AsyncPostgreSQL) → `TokenManager` → `LLMSupplier`(LLMConnectionManager) → `SkillsManager` → `MemorySystem` → `UserSystem` → `ChatManager` → `EmojiCore` → `MessageSender` → `PermissionsManagement` → `ToolCalls` → `MediaProcessor` → `CommandSystem` → `CommandLoader` → `LLMCoordinator`（服务名即类名）→ `GroupChat` → `PrivateChat` → `PluginManager`（最后解析，其 `initialize()` 会扫描并加载 `config.file_path.plugins` 下全部插件）
  6. `_register_message_storage()` — 挂载 `WhitelistMiddleware`（群白名单过滤）到 Pipeline，并接入消息存储（`queue.set_overflow_handler(store_message_to_db)` + `event_bus.on_message(priority=101)(store_message_to_db)`）；`ChatManager` 自身注册为 Pipeline 中间件，负责向 `event._extra` 注入 `group_context` / `private_context`
  7. `_register_at_routes()` — 在 EventBus 上注册两条消息路由（两个聊天入口实例在此方法内直接构造）：
     - `@bus.on_message(rule=AtCommandRule(), priority=10)` → `CommandSystem.dispatch_command(event)`（`@` + `/` 开头的命令；处理完成后置 `event.stop_propagation = True`）
     - `@bus.on_message(priority=100)` → 群聊消息（`_extra` 含 `group_context`）走 `initiativeChat().decision(event, group_context)`（普通聊天 / 主动对话决策）；私聊消息（`_extra` 含 `private_context`）走 `privateChatTrigger().decision(event)`（LLM 私聊，受 `private_chat_white_list` 白名单限制）
     > 注：`AtCommandRule.order=10` < `AlwaysRule.order=50`，命令路由总是先于聊天路由执行
  8. `_platform_manager.start_all()` — 启动所有平台适配器 + EventBus 主循环
  9. `_start_runtime_services()` — 启动 `TimeTriggerSupervisor` 循环，并以受控后台任务（名称 `BotFramework.admin_panel`）启动内置 Web 管理面板（见「Web 管理面板」一节）
  > 注：旧的 `_register_network()` / `_start_network()` 已删除；`EventTrigger`、`message_router`（`core/message_manage.py`）已成遗留代码（不再解析/调用）
- **后台任务管理**: `BotFramework.create_background_task(coro, name=...)` 创建受控后台任务（自动跟踪、异常记录日志、`shutdown` 时统一取消）；`graceful_shutdown()` 使用 `asyncio.shield` 保护关闭流程不被取消；`shutdown()` 幂等，顺序为：停面板（≤8s）→ 取消后台任务 → 停 `TimeTriggerSupervisor` → `container.shutdown()`
- **依赖注入**: 使用模块级单例 `container`（`from atribot.core.service_container import container` = `DIContainer()` 单例）核心 API：

  | 方法 | 说明 | 推荐 |
  |---|---|---|
  | `container.get_by_type(ClassName)` | 按类型获取实例：先精确匹配 `_type_map`，再 `isinstance` 遍历查找 | ✅ **优先使用** |
  | `container.get("ServiceName")` | 按名称获取已解析实例（不存在抛 `ValueError`） | ⚠️ 字符串回退 |
  | `container.exists(name)` | 检查服务是否已注册 | |
  | `container.register(name, obj, cleanup=None)` | 注册已创建的实例（同名覆盖会 warning），可选附带清理回调 | |
  | `container.register_class(cls, name=None)` | 注册类供后续 `resolve()` 自动实例化 + 注入依赖 | |
  | `container.register_factory(cls, factory, name=None)` | 注册自定义工厂函数（替代默认构造器） | |
  | `container.unregister(name)` | 注销服务及其清理回调，同时清理 `_type_map` | |
  | `container.resolve(cls)` | **最核心方法**（见下方详解） | |
  | `container.register_cleanup(name, handler)` | 单独注册清理回调（同名重复抛 `ValueError`） | |
  | `container.shutdown()` | 按**注册逆序**执行所有 cleanup 回调（`reversed` 遍历 `_cleanup_handlers`；不清理回调表，重复调用会重复执行） | |

  **`resolve(cls)` 详细流程**：
  1. 先尝试 `get_by_type(cls)`，若已解析则直接返回
  2. 通过 `ContextVar` 追踪解析栈，检测**循环依赖**（抛出 `RecursionError`）
  3. 查找 `_factories[cls]`（`register_class`/`register_factory` 注册的），若找不到且 `cls` 是类则用 `cls` 自身作为工厂
  4. 若工厂类继承 `ServiceBase` 且覆写了 `factory()` 类方法，则使用自定义工厂
  5. **依赖解析**（`_resolve_kwargs`）：检查工厂函数/构造器的类型注解，从容器中递归 `resolve()` 每个参数类型；参数有默认值且容器无法提供时保留默认值；无类型注解且无默认值的参数会报错
  6. 调用工厂获得实例（支持异步工厂）
  7. 若实例继承 `ServiceBase` 且覆写了 `initialize()`，则解析 `initialize` 的参数并调用
  8. 若实例继承 `ServiceBase` 且覆写了 `cleanup()`，提取为清理回调
  9. 调用 `register(name, instance, cleanup=cleanup)` 注册到容器

  **关键设计点**：
  - `_type_map: dict[type, str]` — 类型→名称映射，`register()` 时自动维护，同名类型覆盖会 warning
  - `_resolving_local: ContextVar` — 协程安全的循环依赖检测，不同协程各自维护独立解析栈
  - `shutdown()` 使用 `reversed(list(self._cleanup_handlers.items()))` 保证**先注册后清理**的顺序

- **ServiceBase 生命周期**（`atribot/core/service_container.py`）：服务可选择继承 `ServiceBase` 基类，它定义了三个可覆写的生命周期钩子：
  ```python
  class ServiceBase:
      @classmethod
      def factory(cls, **kwargs) -> Any:        # 自定义工厂（类方法），可转换容器依赖到 __init__ 参数
          return cls(**kwargs)
      async def initialize(self) -> None: ...   # 异步初始化（resolve 后自动调用）
      async def cleanup(self) -> None: ...      # 异步清理（shutdown 时自动调用）
  ```
  - `factory()` — 若覆写，`resolve()` 会用自定义工厂替代默认构造器典型用法：`AsyncPostgreSQL.factory(config)` 通过 `config` 从容器获取 `atriConfig` 并提取数据库连接参数（`host`/`port`/`user`/`password`，**库名取 `config.database.database`**）
  - `initialize()` — 若覆写，`resolve()` 在实例化后自动调用（同样注入参数），用于异步初始化逻辑
  - `cleanup()` — 若覆写，`resolve()` 自动提取为清理回调注册到容器，`shutdown` 时逆序调用
  - **不强制继承**：即使不继承 `ServiceBase`，只要在 `container.register(name, obj, cleanup=fn)` 时手动传入清理回调即可

- **消息流**: `NapCat`（外部QQ） → 平台适配器（`OneBotAdapter`，支持 WebSocket client/server 与 HTTP） → `MessageQueue` → `Pipeline`（`WhitelistMiddleware` 群白名单过滤 + `ChatManager` 上下文中间件） → `EventBus`（按 `PostType` 分发） → 监听器（存储入库 priority=101 / `AtCommandRule` 命令路由 / `initiativeChat`·`privateChatTrigger` 聊天路由 / 插件 handlers）；群聊由 `GroupChat` 处理，私聊由 `PrivateChat` 处理
- **数据库**: PostgreSQL + `pgvector`（HNSW 1024维，m=16/ef=64）+ `pgroonga` 扩展全异步，使用 `async with db as db:` 上下文管理器Schema 定义在 `docker/db/info.sql`，含自定义枚举 `permission_type`、`memory_category`
- **配置访问**: `atriConfig` 将 JSON 包装为支持点操作的 `ConfigObject`（`assets/config.json`）路径统一通过 `config.file_path.*` 访问，均为 `Path` 对象；多平台连接配置在 `config.platforms.<name>`（`adapter`/`connection_type`/`access_token`/`url`，支持 `WebSocket_client`/`WebSocket_server`/`http`，旧别名 `"WebSocket"` 自动归一）

## 完整服务名称表
| 服务名 | 类型 | 推荐获取方式 | Shutdown | 备注 |
|---|---|---|---|---|
| `log` | `Logger` | `get_by_type(Logger)` | — | 容器初始化时自动注册 |
| `config` | `atriConfig` | `get_by_type(atriConfig)` 或 `get("config")` | — | |
| `HTTPClient` | `HTTPClient` | `get_by_type(HTTPClient)` | — | 异步 HTTP 客户端（`get_bytes`/`post_form`/`post_json`） |
| `database` | `AsyncPostgreSQL` | `get_by_type(AsyncPostgreSQL)` 或 `get("database")` | ✅ `close_pool()` | 需 `async with` 使用 |
| `TokenManager` | `TokenManager` | `get_by_type(TokenManager)` | — | Token 用量统计 |
| `LLMSupplier` | `LLMConnectionManager` | `get_by_type(LLMConnectionManager)` 或 `get("LLMSupplier")` | ✅ `close()` | LLM 供应商连接管理 |
| `LLMCoordinator` | `LLMCoordinator` | `get_by_type(LLMCoordinator)` | — | LLM 调度协调（**服务名即类名**，不存在 `LLMSupervisor` 服务名） |
| `CommandSystem` | `CommandSystem` | `get_by_type(CommandSystem)` | — | 命令注册与解析 |
| `MemorySystem` | `MemorySystem` | `get_by_type(MemorySystem)` | — | 记忆系统门面（聚合 Retriever/Extractor/Consolidator） |
| `SandBox` | `SandBoxBase`（`DockerSandbox` / `NoSandbox` / `E2BSandbox`） | `get_by_type(SandBoxBase)` 或 `get("SandBox")`（先 `exists` 检查） | ✅ `stop()` | 后端由 `sand_box.type` 选定：docker（默认）/ local / e2b；初始化失败不阻断；工具层须惰性获取（见沙盒工具约束） |
| `SkillsManager` | `SkillsManager` | `get_by_type(SkillsManager)` | — | Agent Skills 加载与管理 |
| `MCP` | `ToolManager` | `get_by_type(ToolManager)` 或 `get("MCP")` | ✅ `terminate()` | MCP 通过后台队列（`mcp_service_queue`，init/terminate 指令）异步初始化，支持断线重连 |
| `TimeTriggerSupervisor` | `TimeTriggerSupervisor` | `get_by_type(TimeTriggerSupervisor)` | ✅ `stop()` | 定时任务调度 |
| `UserSystem` | `UserSystem` | `get_by_type(UserSystem)` | — | 用户信息管理 |
| `ChatManager` | `ChatManager` | `get_by_type(ChatManager)` | — | 群聊/私聊上下文管理 |
| `EmojiCore` | `EmojiCore` | `get_by_type(EmojiCore)` | — | 表情系统 |
| `MessageSender` | `MessageSender` | `get_by_type(MessageSender)` | — | AI 输出格式化（LaTeX/表情标签→图片 CQ、回复前缀）+ 发送降级纯文本；注入 `GroupChat`/`PrivateChat` |
| `PermissionsManagement` | `PermissionsManagement` | `get_by_type(PermissionsManagement)` | — | async 创建，权限 0-3 四级 |
| `PlatformManager` | `PlatformManager` | `get_by_type(PlatformManager)` | ✅ `stop_all()` | 多平台适配器管理器（持有 MessageQueue + Pipeline + EventBus），替代旧 `_register_network()`/WebSocket 单例 |
| `PluginManager` | `PluginManager` | `get_by_type(PluginManager)` | ✅ `cleanup()`（卸载全部插件） | 插件系统管理器，`initialize()` 自动扫描加载 `atribot/plugins/` |
| `CommandLoader` | `CommandLoader` | `get_by_type(CommandLoader)` | — | 命令模块加载器；`reload_commands()` 供 `/reload`（authority_level=3）热重载：清 `sys.modules` + 清双注册表后重扫 |
| ~~`EventTrigger`~~ | `EventTrigger` | — | — | **遗留代码**：已被 EventBus + 插件系统取代，不再在解析目标中 |
| ~~`WebSocket`~~ | `WebSocketServer` / `WebSocketClient` | — | — | **遗留代码**：已由 `PlatformManager` 取代（多平台配置见 `config.platforms.*`） |
| `ToolCalls` | `ToolCalls` | `get_by_type(ToolCalls)` 或 `get("ToolCalls")` | ✅ cleanup | 本地工具加载与预设管理 |
| `MediaProcessor` | `MediaProcessor` | `get_by_type(MediaProcessor)` | — | 多模态转文本（image/audio/video → text） |
| `GroupChat` | `GroupChat` | `get_by_type(GroupChat)` | — | 群聊 LLM 对话处理 |
| `PrivateChat` | `PrivateChat` | `get_by_type(PrivateChat)` | — | 私聊 LLM 对话处理 |

## 消息类型系统

### atriMessageEvent 事件信封（处理函数第一参数）
命令、插件与 EventBus 处理函数的**第一个参数固定为** `atriMessageEvent` 及其类型别名（`atribot/core/type/bot_types.py`）：

```python
from atribot.core.type.bot_types import (
    atriMessageEvent,       # 基类（泛型）
    MessageEventEnvelope,   # = atriMessageEvent[MessageEvent]，群聊/私聊消息通用
    GroupMessageEnvelope,   # 群聊消息
    PrivateMessageEnvelope, # 私聊消息
    NoticeEnvelope,         # 通知事件
    RequestEnvelope,        # 请求事件
    MetaEnvelope,           # 元事件
)
```

**常用属性**：

| 属性 | 说明 |
|---|---|
| `event` | 平台事件对象（OneBot 事件，如 `GroupMessageEvent`），含 `message_id`、`llm_formatted_message` 等 |
| `group_id` / `user_id` | 群号 / 发送者 QQ（无则为 `None`） |
| `is_at` | 是否 @ 了 Bot |
| `send_client` | 发送客户端（`SendClientBase`），用于发消息 |
| `source` | 来源平台标识（如 `napcat`） |
| `stop_propagation` | 设为 `True` 中断 EventBus 后续监听器的传播 |
| `prevent_default` | 设为 `True` 阻止默认行为 |
| `chat_scope` | 会话类型 `"group"` / `"private"`（`ChatScope`） |
| `direction` | 消息方向，如 `"incoming"` |
| `_extra` | 通用上下文挂载点（Pipeline 中间件写入，如 `event._extra["group_context"]` / `["private_context"]`） |
| `primeval` / `llm_formatted_message` | 原始事件字典 / AI 可读格式化消息 |
| 时序元数据 | `create_time` / `receive_time` / `process_time`；方法 `update_process_time()`；属性 `age_seconds` / `latency_seconds` / `node_elapsed_seconds` |

**常用方法**：

| 方法 | 说明 |
|---|---|
| `await event.send(SendMessage)` | 发送已构建的类型化消息（自动路由） |
| `event.text("...")` / `event.reply_text("...")` | 纯文本 / 回复+文本消息构建（reply 自动带原消息 ID） |
| `event.image(file, file_name=None, summary=None)` / `event.markdown(text)` | 图片 / Markdown 消息构建 |
| `event.message()` | 创建预填目标 ID 的类型化消息构建器 |
| `event.set_extra(key, value)` / `event.get_extra(key, default)` | 挂载 / 读取上下文数据 |
| `event.is_stale(max_age=300)` / `event.is_discardable(max_latency=60)` | 消息时效判断 |
| `await event.deliver_image(url_img, ...)` | 发送图片到当前会话（群发群、私发私，自动路由） |
| `await event.deliver_file(url_file, name=None, ...)` | 发送文件到当前会话 |
| `await event.deliver_merge_text(message, source="ATRI")` | 发送合并转发文本（长文本防刷屏） |
| `await event.deliver_audio(url_audio, ...)` | 发送语音到当前会话 |
| `await event.deliver_music(type, id=None, ...)` | 分享音乐卡片到当前会话 |

### ChatMessage 对象（内部 LLM 格式化模型）
`ChatMessage`（`atribot/core/type/chat_message_types.py`）仍存在，但**不再是处理函数的入参**，仅用于内部 LLM 消息格式化（`format_for_llm()`）：
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

> **注意**：`sender_nickname` 不是独立字段，通过 `sender_info["nickname"]` 访问

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
| `MFaceSegment` | 商城表情 | `MFaceSegment(data: dict)`（含 summary/emoji_id/url） |
| `ForwardSegment` | 合并转发 | `ForwardSegment(id, content=None)` |
| `JsonSegment` | JSON 卡片 | `JsonSegment(json_data: dict \| str)` |
| `FileSegment` | 文件 | `FileSegment(file: File, file_name=None)` |
| `NodeSegment` | 转发节点 | `NodeSegment(content: list, nickname="ATRI-亚托莉", ...)` |
| `UnknownSegment` | 未适配类型 | `UnknownSegment(type_str, data)` |

> 媒体段说明：`FileMessageSegment`（抽象基类，持有 file/file_name/url/path/file_size）+ `TextDescriptableMixin` 提供 `text_description` 属性（MediaProcessor 识别文本缓存，供非多模态模型复用）；外部通过 `segment.text_description` 读/写

### File 封装类
`File` 是一个 `@dataclass`（`chat_message_types.py`），用于封装文件路径：
```python
@dataclass
class File:
    file: str  # 支持 file://、http(s)://、base64:// 协议前缀
```
- 工厂方法：`File.from_local_path(path)`（自动加 `file://`）、`File.from_url(url)`、`File.from_base64(data)`（自动加 `base64://`）；`File.detect_type(file_str)` 按前缀返回 `local` / `http` / `https` / `base64` / `unknown`

### SendMessage（多模态消息构建）
> **注意**：此处的 `SendMessage` 是多模态消息构建器类（位于 `atribot/core/type/chat_message_types.py`），不再是发送服务。实际发送通过 `atriMessageEvent.send_client`（`SendClientBase`）或 `PlatformManager.send()` 完成

```python
from atribot.core.type.chat_message_types import SendMessage

msg = (SendMessage()
    .add_text("说明文字")
    .add_image("https://...")
    .add_at(123456789)
    .add_reply(987654321)
    .add_markdown("**粗体**"))   # 链式调用，.data 属性 → List[Dict[str, Any]]（OneBot 标准格式）
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
| `is_empty()` / `__len__` / `__bool__` / `__str__` | 判空 / 段数 / 真值判断 / CQ 码字符串 |
| `data` (属性) | 返回 `List[Dict[str, Any]]` |
| `to_json()` | 返回 JSON 字符串 |

> `add_node()` 支持 `id` / `uin` / `name` / `source` / `news` / `prompt` / `time` 等转发节点元信息参数

> **类型化消息**：`GroupMessage` 与 `PrivateMessage`（`chat_message_types.py`）继承自 `SendMessage`，构造时预填目标 ID，可直接 `await event.send(msg)` 或 `await send_client.send(msg)` 发送：
> ```python
> from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage
> msg = GroupMessage(group_id=123456789).add_text("群聊消息")   # 或 PrivateMessage(user_id=...)
> await event.send(msg)
> ```

## 权限体系
`PermissionsManagement`（`atribot/core/command/async_permissions_management.py`；文件名为 async_ 前缀，类名即 `PermissionsManagement`）四级权限：
- `0`：黑名单（被封禁）
- `1`：普通用户（默认）
- `2`：管理员
- `3`：Root 用户

`authority_level` 字段含义：`0`=无限制，`1`=普通用户可用，`2`=管理员，`3`=Root

## Key Extension Patterns

### 1. 添加新命令
- 在 `atribot/commands/<category>/` 下创建目录，`command_loader`（`CommandLoader`）自动扫描并加载各子目录的 `__init__.py`
- **重要**：`CommandLoader` 动态注入父模块时必须设置 `__path__`（否则子模块绝对导入会报"不是包"）；加载命令包时应先执行 `__init__.py`，再加载同级其他 `.py` 文件，避免同包绝对导入失败
- 热重载：`/reload`（别名 `重载` / `reload_commands`，authority_level=3）调用 `CommandLoader.reload_commands()`：清 `sys.modules` 中已加载模块 + 清空命令/别名注册表后重新扫描
- 处理函数**第一个参数固定为** `message_data: MessageEventEnvelope`，通过 `message_data.group_id`、`message_data.user_id` 等属性访问
- **三种参数装饰器**（顺序：register_command → option/argument/flag → 处理函数）：

```python
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system = container.get_by_type(CommandSystem)

@cmd_system.register_command(
    name="cmd",
    description="命令描述",
    authority_level=1,
    aliases=["别名"],
    usage="自定义用法说明",
    examples=["/cmd arg --opt value"]
)
# 位置参数（/cmd value）
@cmd_system.argument(name="param", description="...", required=True, type=str, multiple=False, choices=["a","b"], metavar="PARAM")
# 选项参数（--opt value 或 -o value）
@cmd_system.option(name="opt", short="o", long="--opt", description="...", required=False, default=None, type=str, choices=["x","y"], metavar="VAL")
# 布尔标志（--flag 或 -f，无值）
@cmd_system.flag(name="verbose", short="v", long="--verbose", description="详细输出")
async def handler(message_data: MessageEventEnvelope, param: str, opt: str | None, verbose: bool) -> None:
    # 方式一：事件信封自带发送客户端
    await message_data.send_client.send_group_msg(message_data.group_id, f"Response: {param}")
    # 方式二：快捷回复（自动带 reply 段）
    # await message_data.send(message_data.reply_text(f"Response: {param}"))
```

### 2. LLM Function Calling 工具
- 权威编写说明见 `atribot/LLMchat/tools/README.md`；三种注册方式：
  1. **目录式**：在 `atribot/LLMchat/tools/<tool_name>/` 创建目录 + `__init__.py`，必须导出 `tool_json`（OpenAI function calling 格式）和 `async def main(**kwargs)`；目录名不要以 `_` 开头（扫描器会跳过）
  2. **装饰器式**：`@ToolCalls.register_tool(name=..., concurrent=..., background=...)`（如 `sub_agent`）或 `@ToolCalls.register_dynamic_tool(provider)`（`provider` 运行时返回完整 `tool_json`，用于随环境变化的工具，如沙盒 4 工具）
  3. **沙盒工具**：`sandbox_tools/` 统一实现 `run_python_code` / `run_command` / `send_file` / `add_file`，由 `ToolCalls._load_sandbox_tools()` 按后端动态生成描述与 `active`
- `tool_json` 常用可选字段：`active`（是否启用）、`chat_scope`（`"group"` / `"private"`）、`concurrent`（允许并发）、`background`（后台执行）

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

- **沙盒工具硬约束**：工具模块顶层**禁止** `container.get("SandBox")` —— 工具模块经 `exec_module` 执行且异常会被静默吞掉，会导致工具整体消失；统一在 `sandbox_tools/runtime.py` 内惰性获取（`get_sandbox()` / `require_sandbox()`）
- 刷新入口：`/tools reload`、Web 面板 `POST /api/tools/refresh` 与 `POST /api/sandbox/refresh-tools`；沙盒 start/stop/restart 后自动刷新

**已内置工具（18 个）**：
- 检索 / 记忆：`web_search`、`web_extract`、`memory_search`、`memory_storage`、`get_user_info`、`get_stranger_info`
- 代码 / 沙盒：`run_python_code`（沙盒 Python）、`run_command`（沙盒 Shell）、`send_file`（沙盒内文件送出）、`add_file`（文件上传沙盒）
- 消息 / 互动：`send_image_message`、`send_speech_message`（TTS）、`set_group_ban`、`send_cloud_music`
- 调度 / 协作：`schedule_self_trigger`（定时自触发新群聊思考）、`sub_agent`（子代理）、`load_skill_prompt`、`tool_search`（deferred 工具动态发现，见下一节）
> 注：`send_create_image` 已废弃，源码已删除（`atribot/LLMchat/discard_tools/` 仅剩空目录）

### 3. 工具预设与 deferred 工具发现
- 预设配置位于 `config.tool_presets`，支持两种形态：list（全部默认启用）或 dict `{"default": [...], "deferred": [...]}`；`deferred` 名单中的工具不直接提供给 LLM，而是通过 `tool_search` 动态发现（`tool_search` 自身必须放在 `default`）
- 每轮对话由 `ChatBasics._prepare_round_toolset()` 复制模板 `ToolSet`（`replace()` 为浅拷贝，必须每轮 `copy()`，否则会污染长生命周期模板预设）；`LLMCoordinator.get_chat_json()` 每次 API 请求重读 `request.tool_json`，本轮内动态追加的工具即时生效
- `tool_search` 触发流程：抛 `ToolSearchRequested`（`atribot/core/type/context_types.py`）→ `LLMCoordinator._handle_tool_search_request` → `ToolCalls.enable_deferred_tools(query, limit, target_toolset, preset_name)` 评分并临时加入本轮可用工具，下一轮自动还原
- 相关 API：`ToolCalls.resolve_toolset(preset=...)` / `get_openai(toolset=...)` / `enable_deferred_tools()` / `get_deferred_tools_prompt(preset)`；`ToolSet` 定义于 `atribot/LLMchat/MCP/tool_model.py`；评分函数 `score_tool` 位于 `tool_calls.py` 模块级
- 测试：`tests/test_tool_search.py`

### 4. 定时任务
- 通过 `container.get_by_type(TimeTriggerSupervisor)` 获取调度器，支持一次性延迟、固定间隔、Cron 三种模式：
  ```python
  trigger = container.get_by_type(TimeTriggerSupervisor)
  # 一次性延迟任务（5 秒后执行）
  await trigger.add_task(func=my_async_func, trigger_delta=5.0, remarks="一次性任务")
  # 固定间隔循环任务（每 60 秒执行）
  await trigger.add_task(func=my_func, trigger_delta=0.0, interval=60.0, remarks="每分钟")
  # Cron 表达式任务（每天 9:00）
  await trigger.add_cron_task(func=my_func, cron_expression="0 9 * * *", remarks="每天9点")
  # 取消任务
  trigger.remove_task(task_id)
  ```
- `add_task()` 完整签名：`add_task(func, trigger_delta, task_id=None, priority=10, interval=0.0, timeout=5.0, kwargs=None, remarks="")`
- `add_cron_task()` 完整签名：`add_cron_task(func, cron_expression, task_id=None, priority=10, timeout=5.0, kwargs=None, remarks="")`
- 说明：`TimeTriggerSupervisor` 无持久化能力（未完成任务不跨进程恢复），且未注册容器 cleanup —— 由 `BotFramework.shutdown()` 显式 `stop()`

### 5. Agent Skills
- 在 `atribot/LLMchat/skills/agent_skills/<skill-name>/` 下创建含 YAML frontmatter 的 `SKILL.md`
- 必填字段：`name`（小写字母+数字+`-`）和 `description`；可选：`version`、`author`、`tags`
- 参考说明文档：`atribot/LLMchat/skills/agent_skills/如何创建一个skills.md`
- 技能在运行时通过 `load_skill_prompt` 工具加载给 LLM 使用，也可通过 `container.get_by_type(SkillsManager).get_skill_md_prompt(skill_name)` 直接获取
- **性能说明**：`SkillsManager` 启动时使用 `validator.load_validated_properties()` 一次性完成读取、解析、验证和 `SkillProperties` 构建，避免重复 I/O

### 6. EventBus 事件扩展
- 消息路由由 `EventBus`（`atribot/core/event_bus/bus.py`）负责，通过 `container.get_by_type(PlatformManager).event_bus` 获取
- 监听器按 `(rule.order, -priority)` 排序执行（`priority` 越大越先执行）；规则类见 `atribot/core/event_bus/rule.py`（括号内为 `order`）：`AtCommandRule`(10) / `CommandRule`(20) / `RegexRule`(30) / `GroupRule`(40) / `AlwaysRule`(50) / `UserRule`(50) / `AtRule`(70) / `AndRule` / `OrRule` / `NotRule`(90)
  ```python
  from atribot.core.event_bus.rule import RegexRule
  from atribot.core.platform.manager import PlatformManager
  from atribot.core.service_container import container
  from atribot.core.type.bot_types import MessageEventEnvelope, NoticeEnvelope

  bus = container.get_by_type(PlatformManager).event_bus

  @bus.on_message(rule=RegexRule(r"关键词"), priority=0)
  async def on_keyword(event: MessageEventEnvelope) -> None:
      await event.send(event.reply_text("收到关键词！"))
      # event.stop_propagation = True  # 拦截后续监听器

  @bus.on_notice(priority=0)      # 通知事件（如戳一戳）
  async def on_poke(event: NoticeEnvelope) -> None:
      pass

  @bus.on_request(priority=0)     # 请求事件（如加群申请）
  @bus.on_meta(priority=0)        # 元事件（如心跳）
  @bus.on_message_sent(priority=0)  # 自身发送的消息
  ```
- 也可用通用 `bus.on(PostType, rule=..., priority=..., once=...)`，`PostType` 取自 `atribot/core/type/onebot_event_types.py`；`once=True` 触发后自动移除监听器
- 处理函数签名 `async def handler(event: atriMessageEvent) -> None`；单个监听器异常会被捕获记日志，不影响后续监听器；`stop_propagation` 在分发入口与每个监听器前都会被检查；管线/分发并发上限各 50
- 总线其他 API：`bus.remove_listener(...)` / `bus.clear()` / `bus.listener_count` / `await bus.wait_pending()`
- 自定义规则：继承 `Rule`（`atribot/core/event_bus/rule.py`），实现 `async def match(msg) -> bool` 并声明 `rule_type`/`order` 类属性

### 7. 插件系统（推荐的事件扩展方式）
- 插件目录：`atribot/plugins/<name>/`，`PluginManager` 启动时自动扫描加载；**无需手动注册**，`Plugin.__init_subclass__` 会自动收集事件处理器/中间件并写入注册表
- 在插件包内定义 `Plugin` 子类（`atribot/plugins/plugin.py`）：
  ```python
  from atribot.core.event_bus.rule import RegexRule
  from atribot.core.type.bot_types import MessageEventEnvelope
  from atribot.plugins.plugin import Plugin

  class MyPlugin(Plugin):
      plugin_name = "my_plugin"
      plugin_version = "1.0.0"
      plugin_description = "示例插件"
      plugin_author = "ATRI"

      @Plugin.on_message(rule=RegexRule(r"^你好"), priority=0)
      async def on_hello(self, event: MessageEventEnvelope) -> None:
          await event.send(event.reply_text("你好呀！"))

      @Plugin.middleware(stage="message", name="filter")
      async def my_middleware(self, event: MessageEventEnvelope) -> MessageEventEnvelope | None:
          if ...: return None   # 丢弃消息
          return event
  ```
- **事件装饰器**：`@Plugin.on_message / on_message_sent / on_notice / on_request / on_meta`，签名 `(rule=None, priority=0, once=False)`
- **中间件**：`@Plugin.middleware(stage="message", name="")`，`stage` 声明值 `"message"/"command"/"ai"/"tool"/"http"` —— 目前仅作声明约定，所有中间件**统一挂载到主 Pipeline**（无按 stage 拆分，装饰器也不支持 `priority`）；方法返回 `atriMessageEvent | None`，返回 `None` 则丢弃消息
- **生命周期**：`async def initialize(self)`（加载后调用）、`async def cleanup(self)`（卸载前调用）；实例属性 `self.log`、`self.event_bus`；插件类经 `Plugin.__init_subclass__` 自动收集注册（注册表 key 为 `cls.__module__`），框架文件为 `plugin.py`/`manager.py`/`loader.py`/`registry.py`/`runtime.py`
- **PluginManager API**（`container.get_by_type(PluginManager)`）：`load_plugin(module_path)` / `unload_plugin(module_path)` / `reload_plugin(module_path)`（热重载：清 `sys.modules` 后重新导入，无文件监听）/ `get_plugin(module_path)` / `list_plugins()` / `loaded_plugins`；未初始化时调用抛 `RuntimeError`
- **内置插件**：`emoji_like`（消息贴表情镜像）、`group_manager`（关键词回复 + 群成员变动通知 + 加群审批）、`poke_reaction`（戳一戳反馈）
- 插件可通过 `container.get_by_type(...)` 访问全部核心服务

## SendMessage API（SendClientBase / event.send_client）
> ~~`SendMessage` 服务~~（旧 `QQAPIClient` / `container.get("SendMessage")` 已废弃删除）。发送能力统一走 `atriMessageEvent` 信封体系：事件处理函数中用 `event.send_client`（`SendClientBase`）；广播发送用 `container.get_by_type(PlatformManager).send(GroupMessage(...))`（遍历全部适配器逐个发送）

```python
send_message = message_data.send_client                  # 事件处理函数内
send_message = container.get_by_type(PlatformManager)    # 或用于广播发送

# 基础发送（message 可为 str 或 list[dict]）
await send_message.send_group_msg(group_id, message)
await send_message.send_group_reply_msg(group_id, message, reply_message_id)  # 自动拼接 reply 段
await send_message.send_group_pictures(group_id, url_img, default=False, local_Path_type=True)  # 图片
await send_message.send_group_image(group_id, url_img)      # 图片（简易版）
await send_message.send_group_audio(group_id, url_audio)    # 语音
await send_message.send_group_video(group_id, url_video)    # 视频
await send_message.send_group_file(group_id, url_file, name=None, ...)  # 文件

# 类型化消息发送（自动路由）
await send_message.send(GroupMessage(group_id=...).add_text("..."))
await send_message.send_group(message, echo=False)          # 发送 GroupMessage 对象
await send_message.send_private(message, echo=False)        # 发送 PrivateMessage 对象

# 私聊对应方法（首参为 qq_id，与群聊成对）
await send_message.send_personal_pictures / send_personal_audio / send_personal_file / send_personal_music(...)

# 合并转发
await send_message.send_group_merge_text(group_id, message, source="来源")      # 单文本合并转发
await send_message.send_group_merge_forward(group_id, input_messages, ...)      # 多节点合并转发
await send_message.send_private_merge_text(...) / send_private_merge_forward(...)  # 私聊版本

# 群管理 / 互动
await send_message.set_group_ban(group_id, user_id, duration=1800)  # 禁言（秒）
await send_message.set_group_add_request(flag, approve=True, reason="不行哦!")  # 处理加群申请
await send_message.send_group_poke(group_id, user_id)               # 群戳一戳
await send_message.delete_msg(message_id)                           # 撤回消息
await send_message.set_msg_emoji_like(message_id, emoji_id, set)    # 消息贴表情

# 查询（get_msg_details 返回 MessageEventEnvelope）
await send_message.get_group_info(group_id) / get_stranger_info(qq_id)
await send_message.get_msg_details(message_id)
await send_message.get_img_details(file_id) / get_recordg_details(file, file_id)

# 其它
await send_message.send_group_json(group_id, json_dict)
await send_message.send_group_music(group_id, type, id, ...)
await send_message.async_send(action, params)               # 底层 OneBot action 直发
```

URL 格式：`http(s)://...`、`file://绝对路径`（需 `local_Path_type=True`）、`base64://编码字符串`

> **MessageSender（AI 输出专用格式化发送）**：`container.get_by_type(MessageSender)`（`atribot/LLMchat/message_sender.py`）。`format_text()` 把 LLM 输出转为 CQ 消息：LaTeX 公式（`$...$` / `$$...$$` / `\(...\)` / `\[...\]`）→ codecogs 图片、表情标签 → 图片 CQ、回复引用前缀（`max_emoji=3`）；发送失败时用 `fallback_text()` 剥标签降级重发。主要方法：`send_group_text` / `send_group_text_list` / `send_private_text` / `send_private_text_list`（均需传 `send_client`，列表版支持 `delay` 控制分条间隔，`chat.py` 使用 `MESSAGE_DELAY=1.5`）

## Web 管理面板（web_panel）
- 与 Bot **同进程**运行：`BotFramework._start_runtime_services()` 以受控后台任务（名称 `BotFramework.admin_panel`）启动 FastAPI + uvicorn（`atribot/web_panel/`），路由前缀 `/admin/`；端口被占用或启动失败不影响主服务
- 监听地址/端口取值顺序：环境变量 `ATRI_WEB_PANEL_HOST` / `ATRI_WEB_PANEL_PORT` > `config.web_panel.host` / `port` > 默认 `127.0.0.1:5125`（Docker 部署用 env 绑 `0.0.0.0` 才能从宿主机访问；本仓库 `assets/config.json` 使用 5308，compose 宿主映射默认仅绑 `127.0.0.1`）
- 配置 `config.web_panel`：`enable`（默认启用）、`host`、`port`、`access_token`；关闭时 `_stop_admin_panel()` 等待后台任务退出（≤8s）
- 鉴权（`web_panel/deps.py` + `routes/auth.py` + `session_store.py`）：主令牌（`web_panel.access_token` > 环境变量 `ATRI_PANEL_TOKEN`，**无平台令牌兜底**，未配置时接口 503）仅用于 `POST /api/login` 换取**会话令牌**（内存态、固定有效期默认 4 小时可由 `web_panel.session_ttl_hours` 调 1-24、容量 100、`POST /api/logout` 可吊销、主令牌轮换清空全部会话、前端到点自动退出）；其余 HTTP/WS/query 端点一律只认会话令牌（Bearer / `?token=`）；登录失败**全局计数**（不区分 IP）：连续 3 次触发锁定（10min×2^(n-3) 封顶 24h），锁定期内一律 429（正确口令也拒绝），成功登录清零；已建立 WS 会周期复验会话并以 4401 断开；terminal WS 命令写入 `atri-bot.Terminal` 审计日志
- 路由分 12 组（`web_panel/routes/`）：dashboard（状态/统计）、data、memory（记忆管理）、tools（工具管理/测试）、database、config（config/supplier/mcp 在线编辑，保存前备份 `.bak`）、personas、message、chat（多会话/流式/附件）、system（**仅 `POST /api/system/stop` 优雅关闭，无重启** + `GET /api/ws/logs` 日志流）、terminal（沙盒终端 WS）、sandbox（沙盒管理/刷新工具）
- 开发模式：`python -m atribot.web_panel.dev_server`（mock 环境 + `dev-token`）；接口文档见 `atribot/web_panel/API.md`

## 记忆系统
- `MemorySystem` 是门面类（`atribot/LLMchat/memory/memory_system.py`），内部聚合 `MemoryRetriever`（向量+全文检索）、`MemoryExtractor`（LLM 提取记忆）和 `MemoryConsolidator`（记忆合并去重）；`UserSystem`（用户画像）位于 `memory/user_info_system.py`
- **关键实践**：构建时共享 `MemoryRetriever`/`MemoryExtractor` 实例注入 `MemoryConsolidator`，避免重复初始化 LLM 供应商；相似度边 SQL 聚集逻辑归属 `MemoryRetriever`，`MemoryConsolidator` 仅负责编排聚集/合并流程

**MemoryCategory** 8 种分类（`atribot/LLMchat/RAG/vector_store.py`）：
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

`group_id` 语义：`None` = 知识库，`0` = 私聊，`>0` = 群聊记忆条目含 `importance`（1-10）和 `credibility`（1-10）质量指标，另有 `access_count`/`last_accessed` 检索统计，HNSW 向量索引 + pgroonga 全文索引双重检索

- **高级群聊提取**：`extract_stored_group_message_advanced()` 通过 LLM 做 `add/update/overwrite/skip` 决策，支持批量插入 + 批量更新
- **混合召回**：`hybrid_recall()` —— 向量 + pgroonga 全文各取 top40，RRF 融合后再叠加 importance / access_count / 时间衰减附加分（权重在 `memory_retriever.py`）；`query_memories(category=..., min_importance=..., min_credibility=..., update_stats=...)` 支持质量过滤
- **自动整理**：`MemoryConsolidator` 构建时自动注册 24 小时定时维护任务（`scheduled_memory_maintenance`，task_id=1101），先清理过期记忆再聚类合并；门面暴露 `cleanup_expired_memories()` / `consolidate_memories()`
- **半衰期（时间衰减 λ）**：`group_topic`≈7 天、`emotion`≈30 天、`experience`≈60 天、`fact`/`preference`≈90 天、`knowledge`/`domain`/`guideline`≈10 年

## 数据库 API（AsyncPostgreSQL）
```python
db = container.get_by_type(AsyncPostgreSQL)
async with db as db:
    rows = await db.fetch(sql, params)
    row  = await db.fetchrow(sql, params)
    await db.execute(sql, params)
    # 内置便捷方法
    await db.add_user(user_id, nickname)
    await db.add_message(message_id, content, ...)
    await db.add_group(group_id, group_name)
```
连接参数取自 `config.database`（`host`/`port`/`user`/`password`/`database`，库名默认 `atri`，Docker 部署可用 `ATRI_DB_NAME` 覆盖）
核心表：`users`、`user_group`、`user_info`（JSONB 用户画像）、`permissions`、`message`、`atri_memory`（pgvector 1024维 + importance/credibility + access_count/last_accessed）、`chat_context`（JSONB 上下文）、`token_statistics`（Token 用量统计，配合 `TokenManager`）

## Coding Standards
- **异步优先**: 所有 IO（DB、网络、LLM API）必须使用 `async/await`
- **绝对路径**: 使用 `container.get_by_type(atriConfig).file_path.*` 获取路径，**禁止使用相对路径**
  - 项目路径：`project_root`、`document_root`
  - 核心目录：`commands`、`chat_manager`、`supplier_config_path`、`agent_skills`、`tool_calls`、`mcp_config`、`plugins`
  - 文档目录：`emoji`、`audio`、`img`、`video`、`temp`、`file`
- **日志**: 使用命名子日志器标识模块来源获取方式：`log = container.get_by_type(Logger).getChild("ModuleName")`日志输出格式为 `%(asctime)s [%(levelname)s] atri-bot.ModuleName | %(message)s`统一使用 `self.log`（实例变量）或 `log`（局部/模块级变量），类型注解为 `Logger`
- **类型注解**: 所有函数参数和返回值都需添加类型注解
- **优雅关闭**: 新服务注册后，调用 `container.register_cleanup(name, cleanup_coro)` 注册清理回调（shutdown 按逆序执行）

## Critical Developer Workflows
- **运行 Bot**: 从**项目根目录**执行 `uv run main.py` 或 `python main.py`，路径解析依赖工作目录
- **数据库 Schema**: 修改持久化逻辑前先查看 `docker/db/info.sql`，所有新建表应在此文件定义
- **LLM 供应商配置**: 在 `assets/supplier_config.json` 的 `api` 数组添加条目：`name` + `base_url` + `api_key` + `models` + `model_parameter`（JSON 键为 `models`，dataclass 字段名才是 `model_dict`）；`api_key` 为 list 时走号池轮询；智谱 bigModel 为普通配置条目（**无硬编码注册**；`model_api/bigModel_api.py` 为未引用的死代码）
- **备用模型**: `config.model.standby_model` 列表维护备选模型；切换逻辑在 `chat.py`（`GroupChat`/`PrivateChat` 的请求封装按列表逐个回退，含视觉能力差异处理），`LLMCoordinator` 本身不做降级
- **RAG/Memory**: 记忆系统基于 pgvector 向量检索（Qwen3-Embedding 1024维 + Qwen3-Reranker 重排序），入口为 `container.get_by_type(MemorySystem)`，向量分类参见 MemoryCategory 8 种枚举
- **MCP 服务**: 配置文件路径由 `config.file_path.mcp_config` 指定（`atribot/LLMchat/MCP/mcp_server.json`）；支持 stdio（`command`/`args`/`env`）与 url 型远程服务（默认 SSE；`"transport": "streamable_http"` 切换为 Streamable HTTP）；`active: false` 的服务不会启动；`ToolManager` 通过后台 `mcp_service_queue` 队列管理启停（`{"type": "init"}` / `{"type": "terminate"}`），并支持断线重连；部分包需固定 `"mcp<2"`（如 ms_image_gen_mcp）。配置格式：
  ```json
  {
    "mcpServers": {
      "server_name": {
        "command": "uvx",
        "args": ["..."],
        "env": {"KEY": "VALUE"},
        "active": true
      },
      "remote_name": {"url": "http://...", "transport": "streamable_http", "active": true}
    }
  }
  ```
- **SandBox**: 使用前调用 `container.exists("SandBox")` 检查；后端由 `sand_box.type` 决定：`docker`（默认，镜像默认 `python:3.12-slim`，`atribot/LLMchat/sandbox/Dockerfile` 预装 numpy/pandas/matplotlib/seaborn/pillow/opencv-python-headless/scipy/sympy + ffmpeg/中文字体）/ `none|no_sandbox|local`（本机直执行，工作区在 `document/work`）/ `e2b`；初始化失败不阻断启动；沙盒工具描述按 后端×平台×shell 动态生成，可用 `sand_box.tool_prompts.<工具名>` 覆盖描述、`sand_box.tools.<工具名>: false` 禁用
- **群组白名单**: `config.group_white_list` 控制哪些群接收消息处理（由 `WhitelistMiddleware` 在 Pipeline 层过滤，`root_user_id` 可绕过），`group_initiative_chat_white_list` 控制主动发起对话的群，`group_information_extraction` 指定自动提取话题的群，`private_chat_white_list` 控制哪些用户可触发 LLM 私聊（由 `privateChatTrigger` 在 EventBus 路由层判定，非白名单用户的私聊消息仍会入库和执行命令，只是不进 LLM；`root_user_id` 可绕过）
- **运行测试**: 项目根目录 `uv run python -m pytest tests/ -q`

````
环境里面要运行py代码请使用uv