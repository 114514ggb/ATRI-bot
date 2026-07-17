import asyncio
from collections.abc import AsyncIterator
from logging import Logger
from typing import Awaitable, Callable, Optional

from atribot.core.type.bot_types import Message
from atribot.core.type.onebot_event_types import PostType

MAX_QUEUE_SIZE = 200
"""默认队列容量"""


class MessageQueue:
    """平台消息队列"""

    def __init__(self, maxsize: int = MAX_QUEUE_SIZE):
        self._queue: asyncio.Queue[Message] = asyncio.Queue(maxsize)
        self._overflow_handler: Optional[Callable[[Message], Awaitable[None]]] = None
        self._log: Logger = Logger("MessageQueue")

        self.total_pushed: int = 0
        """累计推入消息数"""
        self.overflow_count: int = 0
        """因队列满进入溢出处理的消息数"""
        self.dropped_count: int = 0
        """因队列满直接丢弃（非 message 类）的消息数"""
        self.stale_dropped: int = 0
        """出队时因过期丢弃的消息数"""

    def set_overflow_handler(self, handler: Callable[[Message], Awaitable[None]]) -> None:
        """设置队列满时的溢出处理器

        Args:
            handler: 异步回调，接收溢出的 Message。
                     集成时通常传入 DB 写入逻辑（只存聊天记录，不处理）
        """
        self._overflow_handler = handler

    async def push(self, msg: Message) -> bool:
        """将消息推入队列

        Args:
            msg: 消息信封

        Returns:
            True  - 成功入队
            False - 队列满，已走溢出处理或丢弃
        """
        self.total_pushed += 1
        try:
            self._queue.put_nowait(msg)
            return True
        except asyncio.QueueFull:
            post_type = msg.event.post_type
            if post_type in (PostType.MESSAGE, PostType.MESSAGE_SENT):
                self.overflow_count += 1
                if self._overflow_handler:
                    try:
                        await self._overflow_handler(msg)
                    except Exception as e:
                        self._log.exception(f"溢出处理器执行失败: {e}")
            else:
                self.dropped_count += 1
                self._log.debug(
                    f"队列满，丢弃 {post_type.value} 事件 "
                    f"(source={msg.source}, event={type(msg.event).__name__})"
                )
            return False

    async def consume(self) -> AsyncIterator[Message]:
        """消费消息的异步生成器

        持续从队列取出 Message,过期消息直接丢弃。
        供 EventBus.run() 等消费者使用。

        Yields:
            未过期的 Message
        """
        while True:
            msg = await self._queue.get()
            if msg.is_discardable():
                self.stale_dropped += 1
                continue
            yield msg

    @property
    def depth(self) -> int:
        """当前队列深度"""
        return self._queue.qsize()

    @property
    def maxsize(self) -> int:
        """队列最大容量"""
        return self._queue.maxsize

    def stats(self) -> dict:
        """返回当前统计信息的快照"""
        return {
            "depth": self.depth,
            "maxsize": self.maxsize,
            "total_pushed": self.total_pushed,
            "overflow_count": self.overflow_count,
            "dropped_count": self.dropped_count,
            "stale_dropped": self.stale_dropped,
        }
