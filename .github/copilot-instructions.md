````instructions
# ATRI-bot AI Coding Instructions

## Architecture Overview
- **Entry Point**: `main.py` → `atribot/bot_framework.py`（`BotFramework.create()` 工厂方法）。所有服务在 `initialize()` 中**严格按顺序**注册，初始化完成后调用 `TimeTriggerSupervisor.start()` 启动定时循环。
- **初始化顺序**: `config` → `TimeTriggerSupervisor` → `MCP` → `database` → `LLMSupplier` → `SkillsManager` → `SandBox`(可选) → `memorySystem` → `UserSystem` → `ChatManager` → `EmojiCore` → `PermissionsManagement` → `WebSocket/HTTP` → `SendMessage` → `EventTrigger` → `CommandSystem` → `CommandLoader` → `ToolCalls` → `LLMSupervisor` → `GroupChat`
- **依赖注入**: 使用单例 `DIContainer`（`atribot/core/service_container.py`），通过 `container.get("ServiceName")` 获取实例，`container.register(name, obj, cleanup=None)` 注册，`container.register_cleanup(name, handler)` 单独注册清理回调，`container.exists(name)` 检查存在，`container.shutdown()` 按**逆序**执行所有 cleanup。
- **消息流**: `NapCat`（外部QQ） → `WebSocketClient`（单例） → `message_router.main()` → 群聊白名单校验 → `PermissionsManagement.check_access()` → `CommandSystem` 或 `EventTrigger` 或 `LLMCoordinator`。目前**仅处理群消息**，私聊直接 `return`。
- **数据库**: PostgreSQL + `pgvector`（HNSW 1024维，m=16/ef=64）+ `pgroonga` 扩展。全异步，使用 `async with db as db:` 上下文管理器。Schema 定义在 `docker/db/info.sql`，含自定义枚举 `permission_type`、`memory_category`。
- **配置访问**: `atriConfig` 将 JSON 包装为支持点操作的 `ConfigObject`（`assets/config.json`）。路径统一通过 `config.file_path.*` 访问，均为 `Path` 对象。

## 完整服务名称表
| 服务名 | 类型 | Shutdown | 备注 |
|---|---|---|---|
| `log` | `Logger` | — | 容器初始化时自动注册 |
| `config` | `atriConfig` | — | |
| `database` | `AsyncPostgreSQL` | ✅ `close_pool()` | 需 `async with` 使用 |
| `SendMessage` | `QQAPIClient` | — | |
| `LLMSupplier` | `LLMConnectionManager` | ✅ `close()` | |
| `LLMSupervisor` | `LLMCoordinator` | — | |
| `CommandSystem` | `CommandSystem` | — | |
| `memorySystem` | `memorySystem` | — | |
| `SandBox` | `DockerSandbox` | ✅ `stop()` | 初始化可能失败，使用前调用 `container.exists("SandBox")` |
| `SkillsManager` | `SkillsManager` | — | |
| `MCP` | `FuncCall` | ✅ `terminate()` | MCP通过后台队列异步初始化 |
| `TimeTriggerSupervisor` | `TimeTriggerSupervisor` | ✅ `stop()` | |
| `UserSystem` | `UserSystem` | — | |
| `ChatManager` | `ChatManager` | — | 群聊上下文管理 |
| `EmojiCore` | `EmojiCore` | — | 表情系统 |
| `PermissionsManagement` | `PermissionsManagement` | — | async 创建，权限 0-3 四级 |
| `EventTrigger` | `EventTrigger` | — | |
| `WebSocket` | `WebSocketServer` 或 `WebSocketClient` | ✅ `close()` | 由 `connection_type` 决定 |

## 消息类型系统

### ChatMessage 对象
处理函数的**第一个参数固定为** `message_data: ChatMessage`（`atribot/core/type/chat_message_types.py`）：
```python
@dataclass
class ChatMessage:
    user_id: int
    group_id: int | None   # None = 私聊
    message_id: int
    segments: List[MessageSegment]   # 消息段列表
    time: int              # Unix 时间戳
    sender_nickname: str
    
    @property
    def llm_formatted_message(self) -> str  # AI 可读格式化消息
    @property
    def primeval(self) -> dict               # 原始事件数据
```

### MessageSegment 消息段类型
| 类名 | 用途 | 构造 |
|---|---|---|
| `TextSegment` | 纯文本 | `TextSegment(text)` |
| `ImageSegment` | 图片 | `ImageSegment(url)` |
| `AtSegment` | @用户 | `AtSegment(user_id)` |
| `ReplySegment` | 回复消息 | `ReplySegment(msg_id)` |
| `RecordSegment` | 语音 | `RecordSegment(url)` |
| `VideoSegment` | 视频 | `VideoSegment(url)` |
| `FaceSegment` | QQ 表情 | `FaceSegment(face_id)` |
| `ForwardSegment` | 合并转发 | `ForwardSegment(id)` |
| `JsonSegment` | JSON 卡片 | `JsonSegment(json_str)` |

### MessageBuilder（多模态消息构建）
```python
from atribot.core.type.context_types import MessageBuilder

msg = (MessageBuilder()
    .add_text("说明文字")
    .add_image("https://...")
    .add_image_base64(base64_data, "image/png")
    .add_audio(base64_data, "wav")
    .build())   # → Dict[str, Any]
```

## 权限体系
`PermissionsManagement`（`AsyncPermissionsManagement`）四级权限：
- `0`：黑名单（被封禁）
- `1`：普通用户（默认）
- `2`：管理员
- `3`：Root 用户

`authority_level` 字段含义：`0`=无限制，`1`=普通用户可用，`2`=管理员，`3`=Root。

## Key Extension Patterns

### 1. 添加新命令
- 在 `atribot/commands/<category>/` 下创建目录，`CommandLoader` 自动扫描并加载各子目录的 `__init__.py`。
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

### 5. EventTrigger 扩展
- 使用装饰器注册钩子，支持带条件 lambda 过滤：
  ```python
  event_trigger = container.get("EventTrigger")
  
  @event_trigger.on_message(condition=lambda data: "关键词" in data.get("raw_message", ""))
  async def handler(message: ChatMessage, data: dict) -> None:
      pass
  
  @event_trigger.on_notice(lambda data: data.get("sub_type") == "poke")
  async def on_poke(message: ChatMessage, data: dict) -> None:
      pass
  
  @event_trigger.on_request(lambda data: data.get("sub_type") == "add")
  async def on_add_group(message: ChatMessage, data: dict) -> None:
      pass
  ```
- 也可以直接在 `atribot/core/event_trigger/event_trigger.py` 的 `processors` 列表中添加 `(条件lambda, 处理协程)` 元组。

## SendMessage API（QQAPIClient）
```python
send_message = container.get("SendMessage")

await send_message.send_group_msg(group_id, message)        # 发送文本
await send_message.send_group_message(group_id, message)    # 同上
await send_message.send_group_audio(group_id, url_audio)    # 发送语音
await send_message.send_group_pictures(group_id, url_img, local_Path_type=False)  # 发送图片
await send_message.send_group_file(group_id, url_file, local_Path_type=True)      # 发送文件
await send_message.send_group_merge_text(group_id, message, source="来源")        # 合并转发
await send_message.get_group_info(group_id)                 # 获取群信息
await send_message.set_group_add_request(flag, approved)    # 处理加群申请
```
URL 格式：`http(s)://...`、`file://绝对路径`（需 `local_Path_type=True`）、`base64://编码字符串`。

## 记忆系统
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
- **MCP 服务**: 配置文件路径由 `config.file_path.mcp_config` 指定（`atribot/LLMchat/MCP/mcp_server.json`），支持 SSE 和 Streamable HTTP，通过后台异步队列独立运行；`active: false` 的服务不会启动。
- **SandBox**: 使用前务必调用 `container.exists("SandBox")` 检查，`DockerSandbox` 初始化失败不阻断启动；沙盒镜像预装 numpy/pandas/matplotlib/pillow/opencv。
- **群组白名单**: `config.group_white_list` 控制哪些群接收消息处理，`group_initiative_chat_white_list` 控制主动发起对话的群，`group_information_extraction` 指定自动提取话题的群。

````