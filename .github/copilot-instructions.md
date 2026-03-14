````instructions
# ATRI-bot AI Coding Instructions

## Architecture Overview
- **Entry Point**: `main.py`  `atribot/bot_framework.py`（`BotFramework.create()` 工厂方法）。所有服务在 `initialize()` 中按顺序注册，存在初始化依赖顺序：`TimeTriggerSupervisor`  `MCP`  `database`  `LLMSupplier`  `memorySystem`  `CommandSystem`  ...
- **依赖注入**: 使用单例 `DIContainer`（`atribot/core/service_container.py`），通过 `container.get("ServiceName")` 获取实例，`container.register(name, obj)` 注册，`container.exists(name)` 检查存在。
- **消息流**: `NapCat`（外部QQ） `WebSocketClient`（单例） `message_router.main()`  `EventTrigger` 或 `CommandSystem` 或 `LLMCoordinator`。目前**仅处理群消息**，私聊直接 `return`。
- **数据库**: PostgreSQL + `pgvector` + `pgroonga` 扩展。全异步，使用 `async with self.db as db:` 上下文管理器。Schema 定义在 `docker/db/info.sql`，含自定义枚举 `permission_type`、`memory_category`。
- **配置访问**: `atriConfig` 将 JSON 包装为支持点操作的 `ConfigObject`（`assets/config.json`）。路径统一通过 `config.file_path.*` 访问，均为 `Path` 对象。

## 完整服务名称表
| 服务名 | 类型 | 备注 |
|---|---|---|
| `log` | `Logger` | 容器初始化时自动注册 |
| `config` | `atriConfig` | |
| `database` | `atriAsyncPostgreSQL` | 需 `async with` 使用 |
| `SendMessage` | `QQAPIClient` | |
| `LLMSupplier` | `LLMConnectionManager` | |
| `LLMsupervisor` | `LLMCoordinator` | 注意小写 `s` |
| `CommandSystem` | `CommandSystem` | |
| `memorySystem` | `memorySystem` | |
| `SandBox` | `DockerSandbox` | 初始化可能失败，使用前调用 `container.exists("SandBox")` |
| `SkillsManager` | `SkillsManager` | |
| `MCP` | `FuncCall` | |
| `TimeTriggerSupervisor` | `TimeTriggerSupervisor` | |
| `UserSystem` | `UserSystem` | |

## Key Extension Patterns

### 1. 添加新命令
- 在 `atribot/commands/<category>/` 下创建目录，`command_loader` 自动扫描并加载各子目录的 `__init__.py`。
- 处理函数**第一个参数固定为** `message_data: ChatMessage`（非 `dict`），通过 `message_data.group_id`、`message_data.user_id` 等属性访问。
- 参数装饰器：`@cmd_system.argument()`（位置/选项）、`@cmd_system.flag()`（布尔开关 `--flag`）。
- `authority_level`: `0`=无限制，`1`=普通（默认），更高=管理员/root。

  ```python
  from atribot.core.service_container import container
  from atribot.core.type.chat_message_type import ChatMessage

  cmd_system = container.get("CommandSystem")
  send_message = container.get("SendMessage")

  @cmd_system.register_command(name="cmd", description="...", authority_level=1, aliases=["别名"])
  @cmd_system.argument(name="param", description="...", required=True, type=str)
  async def handler(message_data: ChatMessage, param: str):
      await send_message.send_group_msg(message_data.group_id, f"Response: {param}")
  ```

### 2. LLM Function Calling 工具
- 在 `atribot/LLMchat/tools/<tool_name>/` 下创建目录 + `__init__.py`。
- 必须导出：`tool_json`（OpenAI function calling 格式，含 `name`/`description`/`properties`）和 `async def main(**kwargs)` 函数，kwargs key 与 `tool_json.properties` 一致。
- 参考实现：`atribot/LLMchat/tools/web_search/__init__.py`。

### 3. 定时任务
- 通过 `container.get("TimeTriggerSupervisor")` 获取调度器，支持一次性、固定间隔、Cron 三种模式：
  ```python
  trigger = container.get("TimeTriggerSupervisor")
  await trigger.add_task(func=my_async_func, interval=60.0, remarks="每分钟")
  await trigger.add_task(func=my_func, cron_expression="0 9 * * *", remarks="每天9点")
  ```

### 4. Agent Skills
- 在 `atribot/LLMchat/skills/agent_skills/<skill-name>/` 下创建含 YAML frontmatter 的 `SKILL.md`。
- 必填字段：`name`（小写字母+数字+`-`）和 `description`。
- 参考说明文档：`atribot/LLMchat/skills/agent_skills/如何创建一个skills.md`。

### 5. EventTrigger 扩展
- 在 `atribot/core/event_trigger/event_trigger.py` 的对应 `processors` 列表中添加 `(条件lambda, 处理协程)` 元组：
  - `message_processors`：消息事件
  - `notice_processors`：通知事件（戳一戳、群成员变动等）
  - `request_processors`：请求事件（加群申请等）

## Coding Standards
- **异步优先**: 所有 IO（DB、网络、LLM API）必须使用 `async/await`。
- **绝对路径**: 使用 `container.get("config").file_path.*` 获取路径，**禁止使用相对路径**。可用字段：`document_root`、`audio`、`img`、`video`、`temp`、`file`、`agent_skills`、`mcp_config` 等。
- **日志**: `log = container.get("log")`，使用 `log.info/warning/error/exception()`。
- **类型注解**: 所有函数参数和返回值都需添加类型注解。
- **优雅关闭**: 新服务在 `BotFramework.initialize()` 中注册后，调用 `self.register_shutdown_handler(name, cleanup_coro)` 注册清理回调。

## Critical Developer Workflows
- **运行 Bot**: 从**项目根目录**执行 `uv run main.py` 或 `python main.py`，路径解析依赖工作目录。
- **数据库 Schema**: 修改持久化逻辑前先查看 `docker/db/info.sql`，所有新建表应在此文件定义。
- **LLM 供应商配置**: 在 `assets/supplier_config.json` 中添加供应商（`base_url` + `api_key` + `model_dict`）。智谱AI（`bigModel`）在 `bot_framework.py` 中硬编码注册，支持 GLM-4.5/4.6V/4.1V 等系列。
- **RAG/Memory**: 记忆系统基于 pgvector 向量检索，入口为 `container.get("memorySystem")`，向量分类由 `MemoryCategory` 枚举定义（`preference/fact/experience/emotion/group_topic/knowledge` 等）。
- **MCP 服务**: 配置文件路径由 `config.file_path.mcp_config` 指定，支持 SSE 和 Streamable HTTP 两种传输协议。

````