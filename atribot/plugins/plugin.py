import logging
from logging import Logger
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from atribot.core.type.onebot_event_types import PostType

from .registry import register
from .types import (
    HandlerDefinition,
    MiddlewareDefinition,
    PluginDefinition,
    PluginMetadata,
)

if TYPE_CHECKING:
    from atribot.core.event_bus.bus import EventBus
    from atribot.core.event_bus.rule import Rule
    from atribot.plugins.runtime import PluginRuntime


class Plugin:
    """插件基类

    使用示例::

        class MyPlugin(Plugin):
            plugin_name = "my_plugin"
            plugin_version = "1.0.0"

            @Plugin.on_message(rule=CommandRule("hello"))
            async def handle_hello(self, msg: atriMessageEvent):
                await msg.send(msg.reply_text("Hello!"))
    """
    plugin_name: str = ""
    """插件名称（留空则取类名）"""

    plugin_version: str = "0.1.0"
    """插件版本号"""

    plugin_description: str = ""
    """插件描述"""

    plugin_author: str = ""
    """插件作者"""


    _definition: ClassVar[PluginDefinition | None] = None
    """类级别的插件定义缓存"""

    _runtime: PluginRuntime | None = None
    """运行时上下文"""

    class _HandlerMarker:
        """包装handler"""
        __slots__ = ('func', 'definition')

        def __init__(self, func: Callable, definition: HandlerDefinition) -> None:
            self.func = func
            self.definition = definition

    class _MiddlewareMarker:
        """包装middleware"""
        __slots__ = ('func', 'definition')

        def __init__(self, func: Callable, definition: MiddlewareDefinition) -> None:
            self.func = func
            self.definition = definition

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # 跳过 Plugin 自身
        if cls.__module__ == Plugin.__module__:
            return

        handlers: list[HandlerDefinition] = []
        middlewares: list[MiddlewareDefinition] = []

        for attr_name, attr in list(cls.__dict__.items()):
            if isinstance(attr, Plugin._HandlerMarker):
                attr.definition.method_name = attr_name
                handlers.append(attr.definition)
                setattr(cls, attr_name, attr.func)

            elif isinstance(attr, Plugin._MiddlewareMarker):
                attr.definition.method_name = attr_name
                middlewares.append(attr.definition)
                setattr(cls, attr_name, attr.func)

        metadata = PluginMetadata(
            plugin_cls=cls,
            module_path=cls.__module__,
            name=cls.plugin_name or cls.__name__,
            version=cls.plugin_version,
            description=cls.plugin_description,
            author=cls.plugin_author,
        )
        register(metadata)

        #缓存
        cls._definition = PluginDefinition(
            plugin_cls=cls,
            metadata=metadata,
            handlers=handlers,
            middlewares=middlewares,
        )

    def __init__(self) -> None:
        """初始化插件实例"""
        self._runtime: PluginRuntime | None = None

    @classmethod
    def on_message(
        cls,
        rule: Rule | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> Callable[[Callable], Callable]:
        """装饰器：标记方法为消息事件处理器"""
        def decorator(func: Callable) -> Callable:
            return Plugin._HandlerMarker(
                func,
                HandlerDefinition(
                    event=PostType.MESSAGE,
                    method_name=func.__name__,
                    rule=rule,
                    priority=priority,
                    once=once,
                ),
            )
        return decorator

    @classmethod
    def on_message_sent(
        cls,
        rule: Rule | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> Callable[[Callable], Callable]:
        """装饰器：标记方法为自身消息发送事件处理器"""
        def decorator(func: Callable) -> Callable:
            return Plugin._HandlerMarker(
                func,
                HandlerDefinition(
                    event=PostType.MESSAGE_SENT,
                    method_name=func.__name__,
                    rule=rule,
                    priority=priority,
                    once=once,
                ),
            )
        return decorator

    @classmethod
    def on_notice(
        cls,
        rule: Rule | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> Callable[[Callable], Callable]:
        """装饰器：标记方法为通知事件处理器"""
        def decorator(func: Callable) -> Callable:
            return Plugin._HandlerMarker(
                func,
                HandlerDefinition(
                    event=PostType.NOTICE,
                    method_name=func.__name__,
                    rule=rule,
                    priority=priority,
                    once=once,
                ),
            )
        return decorator

    @classmethod
    def on_request(
        cls,
        rule: Rule | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> Callable[[Callable], Callable]:
        """装饰器：标记方法为请求事件处理器"""
        def decorator(func: Callable) -> Callable:
            return Plugin._HandlerMarker(
                func,
                HandlerDefinition(
                    event=PostType.REQUEST,
                    method_name=func.__name__,
                    rule=rule,
                    priority=priority,
                    once=once,
                ),
            )
        return decorator

    @classmethod
    def on_meta(
        cls,
        rule: Rule | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> Callable[[Callable], Callable]:
        """装饰器：标记方法为元事件处理器"""
        def decorator(func: Callable) -> Callable:
            return Plugin._HandlerMarker(
                func,
                HandlerDefinition(
                    event=PostType.META,
                    method_name=func.__name__,
                    rule=rule,
                    priority=priority,
                    once=once,
                ),
            )
        return decorator

    @classmethod
    def middleware(
        cls,
        stage: str = "message",
        name: str = "",
    ) -> Callable[[Callable], Callable]:
        """装饰器：标记方法为指定阶段的管道中间件

        中间件在 EventBus 分发之前执行，可以修改或丢弃消息。
        不同阶段的中间件挂载到不同的处理管道。

        Args:
            stage: 中间件阶段。"message" / "command" / "ai" / "tool" / "http"
            name: 中间件名称（留空自动生成 "插件名.方法名"

        使用示例::

            @Plugin.middleware(stage="message", name="filter")
            async def my_middleware(self, msg: atriMessageEvent) -> atriMessageEvent | None:
                if msg.user_id in self.blacklist:
                    return None  # 丢弃黑名单消息
                return msg
        """
        def decorator(func: Callable) -> Callable:
            return Plugin._MiddlewareMarker(
                func,
                MiddlewareDefinition(
                    stage=stage,
                    method_name=func.__name__,
                    name=name,
                ),
            )
        return decorator

    async def initialize(self) -> None:
        """插件加载后调用

        覆写此方法以执行自定义初始化逻辑（如连接外部服务、创建资源）
        无需在此方法中注册事件处理器
        """
        pass

    async def cleanup(self) -> None:
        """插件卸载前调用

        覆写此方法以执行自定义清理逻辑（如关闭连接、释放资源）
        """
        pass

    def unregister_all(self) -> None:
        """从 EventBus 移除所有已注册的事件处理器，从 Pipeline 移除中间件

        委托给 PluginRuntime.unregister_all()
        若未加载运行时，则为空操作
        """
        if self._runtime is not None:
            self._runtime.unregister_all()

    @property
    def log(self) -> Logger:
        """插件日志器

        若已加载运行时，返回运行时的日志器；
        否则返回一个备用日志器，确保插件未加载时也能安全使用
        """
        if self._runtime is not None:
            return self._runtime.log
        return logging.getLogger(f"Plugin.{self.__class__.__name__}")

    @property
    def event_bus(self) -> EventBus:
        """事件总线实例（仅当插件已加载时可用）

        Raises:
            RuntimeError: 插件尚未加载
        """
        if self._runtime is None:
            raise RuntimeError(
                f"插件 '{self.plugin_name}' 尚未加载，无法访问 EventBus"
            )
        return self._runtime.event_bus

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(name={self.plugin_name!r}, version={self.plugin_version!r})"
        )
