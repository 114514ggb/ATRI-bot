import asyncio
from collections import defaultdict
from logging import Logger
from typing import TYPE_CHECKING, Awaitable, Callable

from atribot.core.event_bus.listener import Listener
from atribot.core.event_bus.rule import AlwaysRule, Rule
from atribot.core.platform.message_queue import MessageQueue
from atribot.core.service_container import container
from atribot.core.type.onebot_event_types import PostType

if TYPE_CHECKING:
    from atribot.core.pipeline.pipeline import Pipeline
    from atribot.core.type.bot_types import atriMessageEvent

_RULE_TYPE_ORDER: tuple[str, ...] = (
    "command",
    "regex",
    "group",
    "user",
    "permission",
    "at",
    "always",
    "composite",
    "base",
)


class EventBus:
    """事件总线

    两级索引结构::

        _index[PostType][rule_type] → [Listener(priority=10), Listener(priority=0), ...]

    分发时:
        1. 取出对应 PostType 的所有 rule_type 桶
        2. 按 _RULE_TYPE_ORDER 顺序遍历各桶
        3. 桶内已按 priority 降序排列
        4. 逐个执行 rule.match(msg)，匹配则调用 handler
        5. handler 返回后检查 msg.stop_propagation,为 True 则停止

    Usage::

        bus = EventBus(queue)

        @bus.on(PostType.MESSAGE, rule=CommandRule("help"), priority=10)
        async def help_handler(msg: Message) -> None:
            msg.stop_propagation = True   # 中断后续传播
            ...
    """

    def __init__(self, queue: MessageQueue) -> None:
        self._queue = queue
        self._log: Logger = container.get_by_type(Logger).getChild("EventBus")
        self._running = False

        # 两级索引
        self._index: dict[PostType, dict[str, list[Listener]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._listener_set: set[Listener] = set()


    def on(
        self,
        event_type: PostType,
        rule: Rule | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> Callable:
        """注册事件监听器（装饰器）

        Args:
            event_type: 监听的事件大类
            rule:       匹配规则,None 则用 AlwaysRule
            priority:   优先级（越大越先执行）
            once:       True 表示触发一次后自动注销

        Returns:
            装饰器函数

        Usage::

            @bus.on(PostType.MESSAGE, rule=CommandRule("help"), priority=10)
            async def ping(msg: Message) -> None: ...
        """

        def decorator(
            func: Callable[[atriMessageEvent], Awaitable[None]],
        ) -> Callable[[atriMessageEvent], Awaitable[None]]:
            r = rule if rule is not None else AlwaysRule()
            listener = Listener(
                handler=func,
                event_type=event_type,
                rule=r,
                priority=priority,
                once=once,
            )
            self._add_listener(listener)
            return func

        return decorator

    def _add_listener(self, listener: Listener) -> None:
        """添加监听器并维护索引排序"""
        self._listener_set.add(listener)
        bucket = self._index[listener.event_type][listener.rule.rule_type]
        bucket.append(listener)
        bucket.sort(key=lambda lsnr: -lsnr.priority)  # 降序
        self._log.debug("注册: %s", listener)

    def on_message(
        self, rule: Rule | None = None, priority: int = 0, once: bool = False
    ) -> Callable:
        """注册消息事件处理器"""
        return self.on(PostType.MESSAGE, rule=rule, priority=priority, once=once)

    def on_message_sent(
        self, rule: Rule | None = None, priority: int = 0, once: bool = False
    ) -> Callable:
        """注册自身消息发送事件处理器"""
        return self.on(PostType.MESSAGE_SENT, rule=rule, priority=priority, once=once)

    def on_notice(
        self, rule: Rule | None = None, priority: int = 0, once: bool = False
    ) -> Callable:
        """注册通知事件处理器"""
        return self.on(PostType.NOTICE, rule=rule, priority=priority, once=once)

    def on_request(
        self, rule: Rule | None = None, priority: int = 0, once: bool = False
    ) -> Callable:
        """注册请求事件处理器"""
        return self.on(PostType.REQUEST, rule=rule, priority=priority, once=once)

    def on_meta(
        self, rule: Rule | None = None, priority: int = 0, once: bool = False
    ) -> Callable:
        """注册元事件处理器"""
        return self.on(PostType.META, rule=rule, priority=priority, once=once)

    def remove_listener(self, handler: Callable) -> None:
        """按函数引用移除监听器"""
        for lsnr in [lsnr for lsnr in self._listener_set if lsnr.handler is handler]:
            self._remove_one(lsnr)
            self._log.debug("注销: %s", lsnr)

    def clear(self, event_type: PostType | None = None) -> None:
        """清空监听器

        Args:
            event_type: 为 None 时清空全部；否则只清空该类型
        """
        if event_type is None:
            self._index.clear()
            self._listener_set.clear()
            self._log.info("已清空全部监听器")
        else:
            for lsnr in [lsnr for lsnr in self._listener_set if lsnr.event_type == event_type]:
                self._remove_one(lsnr)
            self._log.info("已清空 %s 监听器", event_type.value)

    def listener_count(self, event_type: PostType | None = None) -> int:
        """查询监听器数量"""
        if event_type is None:
            return len(self._listener_set)
        count = 0
        for lsnr in self._listener_set:
            if lsnr.event_type == event_type:
                count += 1
        return count

    def _remove_one(self, listener: Listener) -> None:
        """从索引和集合中移除单个监听器"""
        self._listener_set.discard(listener)
        bucket = self._index.get(listener.event_type, {}).get(
            listener.rule.rule_type, []
        )
        if listener in bucket:
            bucket.remove(listener)

    async def dispatch(self, msg: atriMessageEvent) -> None:
        """将消息分发给所有匹配的监听器

        Args:
            msg: 待分发的消息信封
        """
        if msg.stop_propagation:
            return

        post_type = msg.event.post_type
        buckets = self._index.get(post_type, {})
        if not buckets:
            self._log.debug("无监听器处理 %s 事件", post_type.value)
            return

        expired: list[Listener] = []

        for rule_type in _RULE_TYPE_ORDER:

            for listener in buckets.get(rule_type, []):
                if msg.stop_propagation:
                    break
                try:
                    if await listener.rule.match(msg):
                        self._log.debug(
                            "触发 %s → %s (rule=%s)",
                            post_type.value,
                            getattr(listener.handler, "__name__", listener.handler),
                            listener.rule,
                        )
                        await listener.handler(msg)
                        if listener.once:
                            expired.append(listener)
                except Exception:
                    self._log.exception(
                        "监听器 %s 执行失败",
                        getattr(listener.handler, "__name__", listener.handler),
                    )

            if msg.stop_propagation:
                break

        # 清理一次性监听器
        for listener in expired:
            self._remove_one(listener)

    async def run(self, pipeline: Pipeline | None = None) -> None:
        """启动事件总线主循环

        Args:
            pipeline: 可选的预处理管道，返回 None 时丢弃该消息
        """
        if self._running:
            self._log.warning("EventBus 已在运行")
            return

        self._running = True
        self._log.info("EventBus 启动，开始消费消息队列")

        try:
            if pipeline:
                async for msg in self._queue.consume():
                    if msg := await pipeline.process(msg):
                        await self.dispatch(msg)
                    continue
            else:
                #这样性能会好些？虽然不太可能会走这边
                async for msg in self._queue.consume():
                    await self.dispatch(msg)
            
        except asyncio.CancelledError:
            self._log.info("EventBus 主循环被取消")
        except Exception:
            self._log.exception("EventBus 主循环异常")
        finally:
            self._running = False
            self._log.info("EventBus 已停止")

    @property
    def is_running(self) -> bool:
        """EventBus 是否正在运行"""
        return self._running
