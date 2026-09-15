# 如何编写命令（Command）

本目录存放 bot 的类 Unix 风格命令。用户发送 **@bot + 以 `/` 开头的消息**（例如 `@atri /help --list`）即可触发命令，命令经 `AtCommandRule` 路由进入 `CommandSystem` 解析执行（见 `atribot/bot_framework.py` 的 `_register_at_routes` 与 `atribot/core/command/command_parsing.py`）。

## 目录约定

- 每个一级子目录是一个分类包：`audio`（音频/TTS）、`bromidic`（杂项娱乐）、`interior`（内部管理）、`test`（实验性）。可以新建自己的分类目录。
- **子目录里必须有 `__init__.py`**（可以是空文件），否则加载器会跳过整个目录。
- 加载器（`atribot/core/command/command_loader.py`）启动时会 import 每个子目录下的**全部 `.py` 文件**，文件名没有强制约定，但惯例是命令注册文件叫 `xxx_command.py` / `xxx_handler.py`，纯业务逻辑不放注册代码。
- 修改命令后无需重启：用 root 权限发送 `/reload` 即可热重载全部命令模块。

## 最小示例

```python
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")


@cmd_system.register_command(
    name="reload",
    description="热重载所有命令模块，无需重启 bot",
    aliases=["重载", "reload_commands"],
    examples=["/reload"],
    authority_level=3,
)
async def reload_commands_handler(message_data: MessageEventEnvelope) -> None:
    loader = container.get("CommandLoader")
    count = loader.reload_commands()
    await message_data.send_client.send_group_msg(
        message_data.group_id, f"✅ 已加载 {count} 个命令包。"
    )
```

（摘自 `interior/reload_command.py`）

## 完整示例：位置参数 + 选项 + flag

```python
@cmd_system.register_command(
    name="tts",
    description="TTS文本合成语音",
    aliases=["语音合成", "说话"],
    examples=["/tts 当然我是高性能的", "/tts -e 机械 -s 0.8 测试文本"],
    authority_level=1,
)
@cmd_system.argument(                      # 位置参数：/tts <TEXT...>
    name="target_text",
    description="需要合成的文本",
    required=True,
    metavar="TEXT",
    multiple=True,                          # 吃掉剩余所有位置参数 → list[str]
)
@cmd_system.option(                         # 带值选项：-e 高兴 / --emotion 高兴
    name="emotion",
    short="e",
    long="emotion",
    description="音频的情感,可选值：高兴, 机械, 平静",
    default="高兴",
    choices=["高兴", "机械", "平静"],
)
@cmd_system.option(
    name="speed",
    short="s",
    type=float,
    default=1.0,
)
async def tts_synthesis(
    message_data: MessageEventEnvelope,
    target_text: list[str],
    emotion: str = "高兴",
    speed: float = 1.0,
):
    ...
```

（摘自 `audio/tts_command.py`）

flag（布尔开关，出现即 `True`）的用法见 `interior/help_command.py`：

```python
@cmd_system.flag(name="list", short="l", long="--list", description="显示所有命令")
```

## 四个装饰器

**装饰器顺序：`register_command` 必须在最上层（最外层），`argument` / `option` / `flag` 叠在它下面。**

### `@cmd_system.register_command(...)`
| 参数 | 说明 |
|---|---|
| `name` | 命令名（注册键，别名映射的目标） |
| `description` | 描述，默认 `"无可用描述"` |
| `aliases` | 别名列表，如 `["帮助"]` |
| `usage` | 自定义用法串（不填则自动生成） |
| `examples` | 示例列表，展示在 `--help` 中 |
| `authority_level` | 最低权限等级，默认 `1` |

### `@cmd_system.argument(...)` — 位置参数
`name` / `description` / `required`（默认 `True`）/ `choices` / `metavar` / `multiple`（吃掉剩余所有位置参数）/ `type`（默认 `str`）。

### `@cmd_system.option(...)` — 带值选项
`name` / `short`（如 `"e"`）/ `long`（默认 `--name`）/ `description` / `required` / `default` / `choices` / `metavar` / `multiple` / `type`。
解析支持 `--opt 值`、`--opt=值`、短选项合并 `-abc`。

### `@cmd_system.flag(...)` — 布尔开关
`name` / `short` / `long` / `description`。出现即 `True`，不出现为 `False`。

## 处理函数签名

```python
async def handler(message_data: MessageEventEnvelope, <参数1>, <参数2>=默认值, ...):
```

- 第一个参数固定是 `message_data`（以关键字注入），类型 `MessageEventEnvelope = atriMessageEvent[MessageEvent]`（定义在 `atribot/core/type/bot_types.py`）。
- 其余形参名与 `argument` / `option` / `flag` 声明的 `name` 对应；**未用装饰器声明的形参也会自动从函数签名提取默认值和类型标注**（见 `command_parsing.py` 中 `Command.__post_init__`）。
- 任意命令带 `--help` / `-h` 时框架自动回复该命令的帮助而不执行，帮助文本由以上元数据自动生成。

## `message_data` 上有哪些东西

常用属性（完整定义见 `atribot/core/type/bot_types.py` 的 `atriMessageEvent`）：

| 属性 | 说明 |
|---|---|
| `event` | 平台事件原始对象（含 `pure_text`、`segments`、`message_id` 等） |
| `group_id` / `user_id` | 群号（私聊为 `None`）/ 用户 QQ |
| `chat_scope` | `"group"` 或 `"private"` |
| `is_at` | 本条消息是否 @ 了 bot |
| `stop_propagation = True` | 中断后续事件监听（命令分发成功后框架会自动置位） |

回复消息两种方式：

1. **信封自带方法**（自动区分群聊/私聊，推荐）：`await message_data.send(message_data.reply_text("文本"))`，以及 `deliver_image` / `deliver_file` / `deliver_merge_text`（长文本自动转合并转发防刷屏）/ `deliver_audio` / `deliver_music`。
2. **`message_data.send_client`**（`SendClientBase`，见 `atribot/core/platform/send_client.py`）：`send_group_msg(group_id, message)`、`send_private_msg(user_id, message)`、`send_group_merge_text(...)`、`send_group_audio(...)`、`send_personal_audio(...)`、`send_group_pictures(...)`、`send_group_file(...)`、`send_group_poke(...)`，以及通用入口 `await send_client.async_send(action, params)` 调任意平台 API。

## 权限等级

定义在 `atribot/core/command/async_permissions_management.py`：

| 等级 | 角色 | 说明 |
|---|---|---|
| 0 | blacklist | 黑名单 |
| 1 | tourist | 普通用户（`authority_level` 默认值） |
| 2 | administrator | 管理员 |
| 3 | root | root（来自 `assets/config.json` 的 `root_user_id`） |

用户等级 ≥ 命令的 `authority_level` 才能执行；等级不足或参数错误时框架自动回复提示。

## 其他依赖服务

需要数据库、配置、日志等时从服务容器获取：

```python
from atribot.core.service_container import container

db = container.get("database")
config = container.get("config")
```

参考实现：`interior/help_command.py`（flag + 自动帮助）、`interior/reload_command.py`（最简）、`audio/tts_command.py`（argument/option 组合）、`bromidic/bili_command.py`（多 flag）、`test/run_command.py`（各种发送 API 演示）。
