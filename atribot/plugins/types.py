from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atribot.core.event_bus.rule import Rule
    from atribot.core.type.onebot_event_types import PostType
    from atribot.plugins.plugin import Plugin
    

@dataclass
class HandlerDefinition:
    """处理器定义（类定义时一次性构建，缓存复用）

    Attributes:
        event: 监听的事件类型
        method_name: 处理函数在插件类上的方法名
        rule: 匹配规则
        priority: 优先级（越大越先执行）
        once: 为 True 时触发一次后自动注销
    """

    event: PostType
    method_name: str
    rule: Rule | None = None
    priority: int = 0
    once: bool = False


@dataclass
class MiddlewareDefinition:
    """中间件定义（类定义时一次性构建，缓存复用）

    Attributes:
        stage: 中间件阶段（"message", "command", "ai", "tool", "http" ...
        method_name: 中间件方法在插件类上的方法名
        name: 中间件名称（用于日志和动态移除）
        priority: 优先级
    """

    stage: str = "message"
    method_name: str = ""
    name: str = ""
    priority: int = 0


@dataclass
class PluginDefinition:
    """插件定义：类级别的结构化描述

    由 Plugin.__init_subclass__ 在类定义时一次性构建并缓存

    Attributes:
        plugin_cls: 插件类引用
        metadata: 插件元数据
        handlers: 处理器定义列表
        middlewares: 中间件定义列表
    """

    plugin_cls: type
    metadata: PluginMetadata
    handlers: list[HandlerDefinition] = field(default_factory=list)
    middlewares: list[MiddlewareDefinition] = field(default_factory=list)


@dataclass
class PluginMetadata:
    """插件元数据（注册表条目）

    存储插件类的引用、路径、元信息
    由 Plugin.__init_subclass__ 自动创建并写入 registry

    Attributes:
        plugin_cls: 插件类引用(Plugin 子类）
        module_path: 模块路径，作为注册表主键
        name: 插件名称
        version: 插件版本号
        description: 插件描述
        author: 插件作者
        enabled: 是否启用
    """

    plugin_cls: type[Plugin]
    module_path: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    enabled: bool = True

    def __repr__(self) -> str:
        return (
            f"PluginMetadata({self.name} v{self.version}, "
            f"module={self.module_path})"
        )
