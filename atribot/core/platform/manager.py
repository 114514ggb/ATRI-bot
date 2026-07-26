import asyncio
import importlib
import logging
import pkgutil
from logging import Logger
from typing import Any

import atribot.core.platform as _platform_pkg
from atribot.core.atri_config import atriConfig
from atribot.core.event_bus.bus import EventBus
from atribot.core.pipeline.pipeline import Pipeline
from atribot.core.platform import _ADAPTER_REGISTRY, get_registered_adapters
from atribot.core.platform.base import PlatformAdapter
from atribot.core.platform.message_queue import MessageQueue
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import SendMessage


class PlatformManager:
    """统一管理所有平台适配器"""

    def __init__(self, config: atriConfig):
        self._log = container.get_by_type(Logger).getChild("PlatformManager")
        self._config = config
        self._adapters: dict[str, PlatformAdapter] = {}
        self._running = False

        self._queue = MessageQueue()
        self._pipeline = Pipeline()
        self._event_bus = EventBus(self._queue,self._pipeline)
        self._bus_task: asyncio.Task[None] | None = None

        self._discover_adapters()
        self._log.info(
            "已发现的适配器类型: %s",
            list(get_registered_adapters().keys()),
        )

        platforms_cfg = config.platforms
        if not platforms_cfg or not platforms_cfg.instances:
            self._log.warning("配置中没有定义任何平台 (config.platforms 为空)")
            return

        for name, plat_cfg in platforms_cfg.instances.items():
            if not plat_cfg.enabled:
                self._log.info("平台 '%s' 已禁用，跳过", name)
                continue

            if not plat_cfg.adapter:
                self._log.warning("平台 '%s' 未指定 adapter 类型，跳过", name)
                continue

            adapter_cls = _ADAPTER_REGISTRY.get(plat_cfg.adapter)
            if adapter_cls is None:
                self._log.warning(
                    "未知适配器类型 '%s' (平台 '%s')，已注册的类型: %s",
                    plat_cfg.adapter,
                    name,
                    list(get_registered_adapters().keys()),
                )
                continue

            adapter = adapter_cls(config=plat_cfg, queue=self._queue)
            self._adapters[name] = adapter
            self._log.info(
                "平台 '%s' 已创建: adapter=%s, connection=%s, source=%s",
                name,
                plat_cfg.adapter,
                plat_cfg.connection_type,
                plat_cfg.source_name,
            )

    @staticmethod
    def _discover_adapters() -> None:
        """扫描 atribot/core/platform/ 下的子包，触发 @register_adapter 装饰器

        通过导入每个子包（如 onebot/），触发其 __init__.py 中
        对适配器类的导入，从而执行 @register_adapter 装饰器
        """
        for _, name, is_pkg in pkgutil.iter_modules(_platform_pkg.__path__):
            if is_pkg:
                try:
                    importlib.import_module(f"atribot.core.platform.{name}")
                except Exception:
                    logging.getLogger("PlatformManager").exception(
                        "导入平台子包 '%s' 失败", name
                    )

    async def start_all(self) -> None:
        """启动所有适配器及 EventBus"""
        if self._running:
            return

        for name, adapter in self._adapters.items():
            self._log.info("启动平台 '%s'...", name)
            try:
                await adapter.start()
            except Exception:
                self._log.exception("启动平台 '%s' 失败", name)

        self._bus_task = asyncio.create_task(
            self._event_bus.run(),
            name="EventBus.main_loop",
        )

        self._running = True
        self._log.info("所有平台已启动 (%d 个),EventBus 已就绪", len(self._adapters))

    async def stop_all(self) -> None:
        """停止所有适配器及 EventBus"""
        self._running = False

        #停止消费新消息
        if self._bus_task and not self._bus_task.done():
            self._bus_task.cancel()
            try:
                await self._bus_task
            except asyncio.CancelledError:
                pass
        self._bus_task = None

        #等待正在分发中的任务完成
        await self._event_bus.wait_pending()

        for name, adapter in self._adapters.items():
            self._log.info("停止平台 '%s'...", name)
            try:
                await adapter.stop()
            except Exception:
                self._log.exception("停止平台 '%s' 失败", name)

        self._log.info("所有平台已停止")

    async def send(self, message: SendMessage) -> dict[str, Any]:
        """向所有适配器发送消息

        遍历所有适配器尝试发送，返回每个适配器的结果

        Args:
            message: 已构建的消息对象

        Returns:
            {平台名: 发送结果}
        """
        results: dict[str, Any] = {}
        for name, adapter in self._adapters.items():
            try:
                results[name] = await adapter.send(message)
            except Exception as e:
                self._log.error("平台 '%s' 发送失败: %s", name, e)
                results[name] = None
        return results

    @property
    def event_bus(self) -> EventBus:
        """共享的事件总线"""
        return self._event_bus

    @property
    def pipeline(self) -> Pipeline:
        """共享的预处理管道"""
        return self._pipeline

    @property
    def queue(self) -> MessageQueue:
        """共享的消息队列"""
        return self._queue

    def get_adapter(self, name: str) -> PlatformAdapter | None:
        """按名称获取适配器实例

        Args:
            name: 平台名称（对应 config.platforms 的 key

        Returns:
            适配器实例，未找到返回 None
        """
        return self._adapters.get(name)

    @property
    def adapters(self) -> dict[str, PlatformAdapter]:
        """所有适配器实例"""
        return dict(self._adapters)

    @property
    def adapter_count(self) -> int:
        """已创建的适配器数量"""
        return len(self._adapters)

    @property
    def is_running(self) -> bool:
        """是否已启动"""
        return self._running
