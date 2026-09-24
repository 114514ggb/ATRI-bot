# 如何编写 LLM 工具（Tool）

本目录存放给大模型 function calling 用的本地工具。聊天时 LLM 可以决定调用这些工具（发图、搜索、记忆存取等），工具的返回值会以 `role=tool` 消息回填给模型继续生成。加载逻辑在 `atribot/LLMchat/MCP/tool_calls.py` 的 `ToolRegistry`。

## 目录约定

- **一个工具 = 本目录下一个子目录，子目录里必须有 `__init__.py`**（复杂工具可在同目录放辅助模块，如 `schedule_self_trigger/trigger_scheduler.py`）。
- `__init__.py` 里必须导出两个东西：
  - `tool_json`（dict）：工具的名称、描述和参数 JSON Schema；
  - `main`（async 函数）：工具执行入口。
- 子目录名不必与工具名一致，**工具名以 `tool_json["name"]` 为准**。
- 废弃的工具移到同级 `LLMchat/discard_tools/` 目录（不在加载路径内）。
- **共享代码包**放在本目录下但需以 `_` 开头（如 `_shared/`）；没有导出 `main`/`tool_json` 的目录（如 `sandbox_tools` 这类共享包、或改用装饰器注册的工具）不会被当作工具注册。
- 工具内**不要**在模块顶层获取可能不存在的服务（如 `container.get("SandBox")`）：`exec_module` 期间的任何异常都会让整个工具从注册表消失。请把获取放到 `main()` 里。

> **沙盒依赖工具已合并**：`run_python_code` / `run_command` / `send_file` /
> `add_file` 不再有独立目录，统一实现在 `sandbox_tools/`（`runtime` / `env` /
> `workspace` / `execution` / `tools`），并由 `ToolCalls` 通过
> `SANDBOX_TOOL_SPECS` 显式注册。

## 全量重载本地工具

本地工具不缓存描述/启用状态，聊天每轮都从注册表现取。需要让工具配置、沙盒
启停或环境变化立即生效时，调用 `ToolCalls.reload_local_tools()`（移除全部
本地工具后重新扫描目录与注册沙盒工具 → 重解析预设 → 重建 schema 缓存）。
当前入口：聊天命令 `/tools reload`、WebUI `POST /api/sandbox/refresh-tools`
与 `POST /api/tools/refresh`。

- 沙盒依赖工具（`run_python_code` / `run_command` / `send_file` / `add_file`）
  在 `sandbox_tools/tools.py` 中定义 handler，描述由
  `sandbox_tools.env.build_tool_json(工具名, properties)` 按后端
  （docker / 本机直执行 / e2b）× 平台在加载/重载时生成，并支持
  `config.json` 的 `sand_box.tool_prompts` 追加或替换。
- MCP 工具不参与重载（其有独立的增量同步/重连回调）。

## 最小示例

`get_user_info/__init__.py` 全文：

```python
from atribot.core.service_container import container
from atribot.LLMchat.memory.user_info_system import UserSystem

tool_json = {
    "name": "get_user_info",
    "description": "用于获取用户的user_info文档,里面包含一些基本信息,如果没有记录的话会返回默认文档",
    "properties": {
        "user_id": {
            "type": "number",
            "description": "用户的唯一标识",
        }
    }
}

user_system: UserSystem = container.get("UserSystem")

async def main(user_id: int):
    return f"用户info的JSON文档:{await user_system.get_user_info(user_id)}"
```

## `main` 的签名

```python
async def main(<参数1>, <参数2>, ..., message_data: atriMessageEvent = None):
```

- 除 `message_data` 外，**形参名必须与 `tool_json["properties"]` 的键一致**，LLM 给出的 JSON 参数会按关键字传入。
- **`message_data` 是可选的上下文注入**：只有当函数签名里声明了 `message_data` 形参，执行器（`MCP/tool_model.py` 的 `LocalTool.execute`）才会自动注入当前会话的信封对象（类型 `atriMessageEvent`，定义在 `atribot/core/type/bot_types.py`）。纯计算类工具（如上例）不需要它。

带 `message_data` 的例子（`send_image_message/__init__.py`）：

```python
from atribot.core.type.bot_types import atriMessageEvent

tool_json = {
    "name": "send_image_message",
    "description": "发送一个url图像到当前会话",
    "properties": {
        "url": {"type": "string", "description": "url链接"}
    }
}

async def main(url: str, message_data: atriMessageEvent) -> str:
    text = await message_data.deliver_image(url, local_Path_type=False)
    return f"发送图像执行结果:{text}"
```

`message_data` 常用成员：

| 成员 | 说明 |
|---|---|
| `event` | 平台事件原始对象 |
| `user_id` / `group_id` | 触发本次对话的用户 / 群（私聊为 `None`） |
| `chat_scope` | `"group"` 或 `"private"` |
| `deliver_image` / `deliver_file` / `deliver_merge_text` / `deliver_audio` / `deliver_music` | 发送便捷方法，自动区分群聊/私聊 |
| `send_client` | 平台发送客户端（`send_group_msg` 等底层 API） |

其他服务（数据库、配置、其他系统）在模块顶部用 `container.get(...)` / `container.get_by_type(...)` 获取，参考 `sandbox_tools/tools.py`。

## `tool_json` 字段说明

必填：

| 字段 | 说明 |
|---|---|
| `name` | 工具名（注册与去重的键，LLM 调用时使用） |
| `description` | **给模型看的**工具用途描述，务必写清楚"什么情况下该用它"，直接影响调用质量 |
| `properties` | 参数的 JSON Schema（OpenAI function calling 格式），每个参数给 `type` + `description` |

可选（由加载器读取）：

| 字段 | 默认 | 说明 |
|---|---|---|
| `chat_scope` | `"both"` | `"group"` / `"private"` / `"both"`，按会话类型过滤可见性 |
| `active` | `True` | 设为 `False` 则不进入 schema，模型看不到 |
| `concurrent` | `False` | 标记可并行执行（批量执行引擎用） |
| `background` | `False` | 标记为后台任务 |

## 返回值与异常

- 返回任意值即可，**会被转成字符串作为工具结果回给 LLM**，超过 20000 字符自动截断。惯例返回 `f"xxx执行结果:{...}"` 这样带上下文的字符串，方便模型理解。
- 特殊控制流（高级）：`tool_search` 工具通过抛 `ToolSearchRequested` 实现工具发现，参考 `tool_search/__init__.py`。
- 工具抛出的普通异常会被上层捕获并作为错误信息回给模型，注意不要在异常里泄露敏感内容。

## 另一种注册方式：装饰器

除了放目录里，也可以用装饰器直接注册（见 `sub_agent/__init__.py`）：

```python
from atribot.LLMchat.MCP.tool_calls import ToolCalls

@ToolCalls.register_tool(
    name="sub_agent",
    description="...",
    properties={...},
    concurrent=True,
    background=True,
)
async def sub_agent(...):
    ...
```

一般场景用目录方式即可，装饰器适合需要闭包/复用已有函数的情况。

## 工具怎么被模型看到（预设机制）

工具不是全部直接暴露给模型。`assets/config.json` 的 `tool_presets` 为 `group_chat` / `private_chat` 各定义了两个集合（由 `ToolPresetManager` 管理）：

- `default`：直接进入本轮请求的 tools schema；
- `deferred`：只在提示词里列出名字，模型需要先调用 `tool_search` 按关键词发现后才会在本轮临时启用。

管理入口：

- 聊天命令 `/tools list|add_tool|del_tool|reload`（需管理员权限，见 `atribot/commands/interior/manage_tools.py`）；
- WebUI 工具管理页（`atribot/web_panel/routes/tools.py`），可在面板里查看和测试工具（声明了 `message_data` 的工具因依赖会话上下文，不支持面板测试）。

## 参考实现

- 纯参数工具：`get_user_info`、`memory_search`
- 会话上下文发送类：`send_image_message`、`send_speech_message`、`send_cloud_music`
- 限定会话类型：`set_group_ban`（`"chat_scope": "group"`）
- 装饰器注册 + 辅助模块：`sub_agent`、`schedule_self_trigger`
- 动态装饰器注册（环境描述）：`sandbox_tools/tools.py`（`run_python_code` / `run_command` / `send_file` / `add_file`）
- JSON Schema 的 strict 模式写法另见 `atribot/docs/LLM_tool.md`
