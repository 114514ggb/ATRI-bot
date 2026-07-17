import asyncio
from collections import defaultdict
from logging import Logger
from typing import Callable, Dict, List, Optional, Tuple

from atribot.core.service_container import container
from atribot.core.type.bot_types import Message
from atribot.core.type.onebot_event_types import PostType

from .message_queue import MessageQueue


class EventBus:
    """事件总线"""

    def __init__(self, queue: MessageQueue):
        self._queue = queue
        self._log: Logger = container.get_by_type(Logger).getChild("EventBus")
        self._running: bool = False

        # post_type → [(condition, handler), ...]
        self._handlers: Dict[PostType, List[Tuple[Callable, Callable]]] = defaultdict(list)

    def on(
        self,
        event_type: PostType,
        condition: Optional[Callable[[Message], bool]] = None,
    ) -> Callable:
        """注册事件处理器的通用装饰器

        Args:
            event_type: 要监听的事件类型(PostType 枚举）
            condition: 可选的条件过滤函数，签名 `(msg: Message) -> bool`
                       为 None 时接受所有该类型事件

        Returns:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            self._handlers[event_type].append(
                (condition if condition is not None else (lambda _: True), func)
            )
            self._log.debug(
                f"注册处理器: {func.__name__} 监听 {event_type.value}"
                f"{' (带条件)' if condition else ''}"
            )
            return func
        return decorator

    def on_message(self, condition: Optional[Callable[[Message], bool]] = None) -> Callable:
        """注册消息事件 (message) 处理器"""
        return self.on(PostType.MESSAGE, condition)

    def on_message_sent(self, condition: Optional[Callable[[Message], bool]] = None) -> Callable:
        """注册自身消息发送事件 (message_sent) 处理器"""
        return self.on(PostType.MESSAGE_SENT, condition)

    def on_notice(self, condition: Optional[Callable[[Message], bool]] = None) -> Callable:
        """注册通知事件 (notice) 处理器"""
        return self.on(PostType.NOTICE, condition)

    def on_request(self, condition: Optional[Callable[[Message], bool]] = None) -> Callable:
        """注册请求事件 (request) 处理器"""
        return self.on(PostType.REQUEST, condition)

    def on_meta(self, condition: Optional[Callable[[Message], bool]] = None) -> Callable:
        """注册元事件 (meta_event) 处理器"""
        return self.on(PostType.META, condition)

    async def dispatch(self, msg: Message) -> None:
        """将单条消息分发给所有符合条件的处理器

        Args:
            msg: 待处理的消息信封
        """
        post_type = msg.event.post_type
        handlers = self._handlers.get(post_type, [])
        if not handlers:
            self._log.debug(f"无处理器处理 {post_type.value} 事件")
            return

        for condition, handler in handlers:
            if not condition(msg):
                continue
            try:
                self._log.debug(
                    f"分发 {post_type.value} → {handler.__name__} "
                    f"(event={type(msg.event).__name__})"
                )
                if await handler(msg):
                    self._log.debug(f"处理器 {handler.__name__} 已拦截")
                    break
            except Exception as e:
                self._log.exception(
                    f"处理器 {handler.__name__} 执行失败: {e}"
                )

    async def run(self) -> None:
        """启动事件分发主循环"""
        if self._running:
            self._log.warning("EventBus 已在运行")
            return

        self._running = True
        self._log.info("EventBus 启动，开始消费消息队列")

        try:
            async for msg in self._queue.consume():
                await self.dispatch(msg)
        except asyncio.CancelledError:
            self._log.info("EventBus 主循环被取消")
        except Exception as e:
            self._log.exception(f"EventBus 主循环异常: {e}")
        finally:
            self._running = False
            self._log.info("EventBus 已停止")

    @property
    def is_running(self) -> bool:
        """EventBus 是否正在运行"""
        return self._running
