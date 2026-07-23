import logging
from logging import Logger
from typing import TYPE_CHECKING, Any, Callable

from atribot.core.pipeline.middleware import PipelineMiddleware

if TYPE_CHECKING:
    from atribot.core.event_bus.bus import EventBus
    from atribot.core.pipeline.pipeline import Pipeline
    from atribot.core.type.bot_types import atriMessageEvent
    from atribot.plugins.plugin import Plugin
    from atribot.plugins.types import PluginDefinition


class PluginRuntime:
    """插件运行时上下文

    管理插件实例的 EventBus 监听器注册、Pipeline 中间件注册及生命周期清理
    每个加载的插件实例对应一个 PluginRuntime,由 PluginLoader 创建

    Attributes:
        plugin: 关联的插件实例
        definition: 插件的类级定义（缓存）
    """

    def __init__(
        self,
        plugin: Plugin,
        definition: PluginDefinition,
        event_bus: EventBus,
        pipeline: Pipeline,
        log: Logger | None = None,
    ) -> None:
        self._plugin = plugin
        self._definition = definition
        self._event_bus = event_bus
        self._pipeline = pipeline
        self._log: Logger = log or logging.getLogger(
            f"Plugin.{plugin.__class__.__name__}"
        )
        self._listener_handlers: list[Callable[..., Any]] = []
        self._middleware_instances: list[PipelineMiddleware] = []

        # 反向绑定到 Plugin 实例
        plugin._runtime = self 

    async def setup(self) -> None:
        """注册 definition 中所有 handlers 和 middlewares

        在调用 ``plugin.initialize()`` 之前执行
        """
        self._register_handlers()
        await self._register_middlewares()

    def _register_handlers(self) -> None:
        """将 definition.handlers 注册到 EventBus"""
        for h in self._definition.handlers:
            handler = getattr(self._plugin, h.method_name)
            self._event_bus.on(
                h.event, rule=h.rule, priority=h.priority, once=h.once
            )(handler)
            self._listener_handlers.append(handler)

            self._log.debug(
                "注册处理器: %s.%s → %s%s",
                self._plugin.__class__.__name__,
                h.method_name,
                h.event.value,
                f" rule={h.rule!r}" if h.rule else "",
            )

    async def _register_middlewares(self) -> None:
        """将 definition.middlewares 注册到 Pipeline

        每个中间件包装为 PipelineMiddleware 匿名子类，
        按 stage 挂载（目前均注册到主 Pipeline,后续可按 stage 分发）
        """
        for m in self._definition.middlewares:
            handler = getattr(self._plugin, m.method_name)
            full_name = m.name or f"{self._plugin.plugin_name}.{m.method_name}"

            class _PluginMiddleware(PipelineMiddleware):
                name = full_name

                async def process(
                    self_, msg: atriMessageEvent
                ) -> atriMessageEvent | None:
                    return await handler(msg)

            mw = _PluginMiddleware()
            await self._pipeline.add_middleware(mw)
            self._middleware_instances.append(mw)

            self._log.debug(
                "注册中间件: %s.%s (stage=%s) → %s",
                self._plugin.__class__.__name__,
                m.method_name,
                m.stage,
                full_name,
            )

    async def unregister_all(self) -> None:
        """从 EventBus 移除所有已注册的事件处理器，从 Pipeline 移除中间件"""
        for handler in self._listener_handlers:
            try:
                self._event_bus.remove_listener(handler)
            except (ValueError, Exception):
                self._log.debug("注销处理器时出错（可能已移除）: %s", handler)
        self._listener_handlers.clear()

        for mw in self._middleware_instances:
            try:
                await self._pipeline.remove_middleware(mw.name)
            except (ValueError, Exception):
                self._log.debug("移除中间件时出错（可能已移除）: %s", mw.name)
        self._middleware_instances.clear()

        self._log.info("已清理所有 EventBus 监听器和 Pipeline 中间件")

    @property
    def log(self) -> Logger:
        """运行时日志器"""
        return self._log

    @property
    def event_bus(self) -> EventBus:
        """事件总线实例"""
        return self._event_bus

    @property
    def plugin(self) -> Plugin:
        """关联的插件实例"""
        return self._plugin

    def __repr__(self) -> str:
        return (
            f"PluginRuntime(plugin={self._plugin.plugin_name!r}, "
            f"handlers={len(self._listener_handlers)}, "
            f"middlewares={len(self._middleware_instances)})"
        )
