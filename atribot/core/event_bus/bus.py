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

MAX_PIPELINE_CONCURRENCY = 50
"""最大并发 pipeline 处理数"""

MAX_DISPATCH_CONCURRENCY = 50
"""最大并发分发数"""


class EventBus:
    """事件总线

    扁平索引结构::

        _dispatch_index[PostType] → [Listener(order=10, priority=10), ...]

    注册时:
        1. 追加到对应 PostType 的列表
        2. 按 (rule.order, -priority) 排序

    分发时:
        1. 取出对应 PostType 的已排序列表，创建 tuple 快照
        2. 逐个执行 rule.match(msg)，匹配则调用 handler
        3. handler 返回后检查 msg.stop_propagation,为 True 则停止
    """

    def __init__(
        self,
        queue: MessageQueue,
        pipeline:Pipeline,
        process_concurrency: int = MAX_PIPELINE_CONCURRENCY,
        dispatch_concurrency: int = MAX_DISPATCH_CONCURRENCY,
    ) -> None:
        self._queue = queue
        self._log: Logger = container.get_by_type(Logger).getChild("EventBus")
        self._running = False

        #扁平索引
        self._dispatch_index: dict[PostType, list[Listener]] = defaultdict(list)
        self._listener_set: set[Listener] = set()

        #并发控制
        self._process_semaphore = asyncio.Semaphore(process_concurrency)
        self._dispatch_semaphore = asyncio.Semaphore(dispatch_concurrency)

        self._pending_tasks: set[asyncio.Task[None]] = set()
        """任务追踪（一条消息一个 task,pipeline+dispatch 全走完才算完成）"""

        self.pipeline = pipeline
        """分发前管道"""


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
            listener = Listener(
                handler=func,
                event_type=event_type,
                rule= rule if rule is not None else AlwaysRule(),
                priority=priority,
                once=once,
            )
            self._add_listener(listener)
            return func

        return decorator

    def _add_listener(self, listener: Listener) -> None:
        """添加监听器并维护排序"""
        self._listener_set.add(listener)
        bucket = self._dispatch_index[listener.event_type]
        bucket.append(listener)
        bucket.sort(key=lambda lsnr: (lsnr.rule.order, -lsnr.priority))
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
            self._dispatch_index.clear()
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
        if bucket := self._dispatch_index.get(listener.event_type):
            try:
                bucket.remove(listener)
            except ValueError:
                pass  # 并发场景下可能已被其他 task 移除

    async def dispatch(self, msg: atriMessageEvent) -> None:
        """将消息分发给所有匹配的监听器

        使用 tuple 快照防止 _dispatch_index 在迭代中被修改。
        """
        if msg.stop_propagation:
            return

        post_type = msg.event.post_type
        listeners = self._dispatch_index.get(post_type)
        if not listeners:
            return

        for listener in tuple(listeners):
            if msg.stop_propagation:
                break
            try:
                if not await listener.rule.match(msg):
                    continue

                #执行前从索引移除，防止并发重复触发
                if listener.once:
                    self._remove_one(listener)

                # self._log.debug(
                #     "触发 %s → %s (rule=%s)",
                #     post_type.value,
                #     getattr(listener.handler, "__name__", listener.handler),
                #     listener.rule,
                # )
                await listener.handler(msg)

            except Exception:
                self._log.exception(
                    "监听器 %s 执行失败",
                    getattr(listener.handler, "__name__", listener.handler),
                )

    async def run(self) -> None:
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
            async for msg in self._queue.consume():
                await self._process_semaphore.acquire()
                self._start_message_task(msg)

        except asyncio.CancelledError:
            self._log.info("EventBus 主循环被取消")
        except Exception:
            self._log.exception("EventBus 主循环异常")
        finally:
            self._running = False
            self._log.info(
                "EventBus 主循环已退出（尚有 %d 个任务正在运行）", len(self._pending_tasks)
            )

    async def wait_pending(self) -> None:
        """等待所有正在处理的任务完成"""
        if self._pending_tasks:
            self._log.info("等待 %d 个任务完成...", len(self._pending_tasks))
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._log.info("所有任务已完成")

    def _start_message_task(self, msg: atriMessageEvent) -> None:
        """为单条消息启动处理任务"""
        task = asyncio.create_task(self._handle_message(msg))
        self._pending_tasks.add(task)
        task.add_done_callback(self._on_task_done)

    async def _handle_message(self, msg: atriMessageEvent) -> None:
        """处理单条消息"""
        try:
            try:
                msg = await self.pipeline.process(msg)
            except Exception:
                self._log.exception("Pipeline 处理消息失败")
                return
        finally:
            self._process_semaphore.release()

        if msg is None:
            return

        async with self._dispatch_semaphore:
            await self.dispatch(msg)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        """消息处理任务完成回调"""
        self._pending_tasks.discard(task)
        if task.cancelled():
            return
        exc: BaseException | None = task.exception()
        if exc:
            self._log.exception("消息处理任务异常: %s", exc)

    @property
    def is_running(self) -> bool:
        """EventBus 是否正在运行"""
        return self._running