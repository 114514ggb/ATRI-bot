# 如何编写插件（Plugin）

插件是挂在事件总线上的常驻模块：订阅消息/通知/请求等事件并做出反应（戳一戳回应、群管理、表情点赞……），也可以注册管道中间件拦截消息。框架文件都在本目录：`plugin.py`（基类）、`loader.py`（发现与加载）、`registry.py`（注册表）、`runtime.py`（运行时）、`manager.py`（服务门面）、`types.py`（数据类）。

## 目录约定

- **一个插件 = 本目录下一个子目录（Python 包）**，命名如 `poke_reaction/`。
- 子目录的 `__init__.py` 里导入定义插件类的模块，让类定义被执行到（惯例：类放 `plugin.py`，`__init__.py` 写 `from .plugin import XxxPlugin`）。
- 类定义即注册：`Plugin.__init_subclass__` 会在类定义时自动收集装饰器标记的处理器/中间件并写入注册表，**不需要手动调用任何注册函数**。
- 启动时 `PluginManager` 扫描本目录的全部子包并自动加载（`manager.py`）；没有文件监听，热重载需显式调用 `PluginManager.reload_plugin("atribot.plugins.<子目录名>")`。

## 最小示例

目录结构：

```
plugins/poke_reaction/
├── __init__.py          # from .plugin import PokeReactionPlugin
├── plugin.py            # 插件类
└── reactivity_list.py   # 纯数据（可选）
```

`plugin.py` 全文：

```python
import random

from atribot.core.type.bot_types import NoticeEnvelope
from atribot.core.type.onebot_event_types import GroupPokeEvent, PokeEvent
from atribot.plugins.plugin import Plugin
from atribot.plugins.poke_reaction.reactivity_list import reactivity_list


class PokeReactionPlugin(Plugin):
    """戳一戳反馈插件"""

    plugin_name = "poke_reaction"
    plugin_version = "1.0.0"
    plugin_description = "戳一戳自动回复与回戳"
    plugin_author = "ATRI"

    @Plugin.on_notice(priority=0)
    async def on_poke(self, event: NoticeEnvelope) -> None:
        ev = event.event
        if not isinstance(ev, PokeEvent):
            return
        if ev.target_id != ev.self_id:      # 只处理戳到 bot 自己的
            return

        text = random.choice(reactivity_list)
        if isinstance(ev, GroupPokeEvent):
            await event.send_client.send_group_msg(ev.group_id, text)
            await event.send_client.send_group_poke(ev.group_id, ev.user_id)
        else:
            await event.send_client.send_private_msg(ev.user_id, text)
```

## 插件类结构

**元数据类属性**（任选，`plugin_name` 留空取类名）：

```python
plugin_name = "my_plugin"        # 插件名
plugin_version = "1.0.0"         # 版本
plugin_description = "……"        # 描述
plugin_author = "……"             # 作者
```

**生命周期钩子**（覆写即可，均可省略）：

```python
async def initialize(self) -> None:
    """插件加载后调用：连接外部服务、读取配置等。处理器注册不在这里做。"""

async def cleanup(self) -> None:
    """插件卸载前调用：关闭连接、释放资源。"""
```

`__init__` 中可以正常做同步初始化（取 DI 服务、读配置文件），参考 `group_manager/plugin.py`（从 `container.get_by_type(PermissionsManagement)` 拿权限系统）。

## 事件订阅装饰器

全部是 `Plugin` 的类方法装饰器，参数一致：`rule: Rule | None`、`priority: int = 0`（越大越先执行）、`once: bool = False`（触发一次后自动注销）。

| 装饰器 | 订阅的事件 | 回调收到的信封类型 |
|---|---|---|
| `@Plugin.on_message(...)` | 别人发的消息 | `MessageEventEnvelope` |
| `@Plugin.on_message_sent(...)` | bot 自己发出的消息 | `MessageEventEnvelope` |
| `@Plugin.on_notice(...)` | 通知（戳一戳、群成员变动、表情回应等） | `NoticeEnvelope` |
| `@Plugin.on_request(...)` | 请求（加好友、加群） | `RequestEnvelope` |
| `@Plugin.on_meta(...)` | 元事件（心跳/生命周期） | — |

信封类型是 `atribot/core/type/bot_types.py` 里的 `atriMessageEvent[...]` 别名。回调内先取 `event.event` 拿到具体事件对象，再用 `isinstance` 分发到具体类型（`PokeEvent`、`GroupPokeEvent`、`GroupIncreaseEvent`、`GroupRequestEvent` 等，全部定义在 `atribot/core/type/onebot_event_types.py`）。

### 规则（Rule）

`rule` 用来过滤事件，可用的现成规则在 `atribot/core/event_bus/rule.py`：

- `CommandRule("hello")` — 文本等于指定词
- `RegexRule(pattern)` — 正则匹配
- `GroupRule(group_id)` / `UserRule(user_id)` — 按群/用户过滤
- `AtRule()` — @ 了 bot
- `AndRule` / `OrRule` / `NotRule` — 组合规则

也可以自定义：继承 `Rule` 实现 `async def match(self, msg) -> bool`，参考 `emoji_like/plugin.py` 的 `EmojiLikeNoticeRule`。

## 中间件

```python
@Plugin.middleware(stage="message", name="filter")
async def my_middleware(self, msg: MessageEventEnvelope) -> MessageEventEnvelope | None:
    if msg.user_id in self.blacklist:
        return None          # 返回 None 即丢弃该消息
    return msg               # 也可以修改后返回
```

`stage` 可选 `"message" / "command" / "ai" / "tool" / "http"`（当前实现统一挂到主 Pipeline，在 EventBus 分发之前执行）。

## 发消息

- 回调内（推荐）：`await event.send(event.reply_text("文本"))` 或 `await event.send(event.text(...))` 构建后发送；底层走 `event.send_client.send_group_msg(group_id, msg)` / `send_private_msg(user_id, msg)`，以及 `send_group_poke`、`set_msg_emoji_like` 等（完整清单见 `atribot/core/platform/send_client.py` 的 `SendClientBase`）。
- 任意位置主动发：`container.get_by_type(PlatformManager)` 取平台适配器再拿 send_client。

## 其他

- `self.log` — 插件专属 logger，任何阶段都可安全使用；`self.event_bus` — 事件总线（仅在插件已加载后可访问）。
- 在回调里给 `event.stop_propagation = True` 可中断后续监听器。
- 卸载/重载由 `PluginManager` 提供：`load_plugin / unload_plugin / reload_plugin(module_path) / list_plugins`；`reload_plugin` 会清掉 `sys.modules` 与注册表后重新导入。
- 插件里也可以注册命令或 LLM 工具：插件加载时 `CommandSystem`、`ToolCalls` 等服务已就绪，在 `initialize()` 里 `container.get("CommandSystem")` / 导入 `ToolCalls` 装饰器即可，写法分别见 `atribot/commands/README.md` 和 `atribot/LLMchat/tools/README.md`。

## 参考实现

- `poke_reaction/` — 最小通知插件（on_notice + isinstance 分发）
- `emoji_like/` — 自定义 Rule + on_notice
- `group_manager/` — 完整示例：`__init__` 取 DI 服务、读 JSON 配置、组合 on_message / on_notice / on_request
