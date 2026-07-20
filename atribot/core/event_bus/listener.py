from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from atribot.core.event_bus.rule import Rule
    from atribot.core.type.bot_types import Message
    from atribot.core.type.onebot_event_types import PostType


@dataclass
class Listener:
    """事件监听器

    Attributes:
        handler:     异步处理函数，签名 `async (msg: Message) -> None`
        event_type:  监听的事件大类 (PostType)
        rule:        匹配规则
        priority:    优先级，越大越先执行，默认 0
        once:        为 True 时触发一次后自动注销
    """

    handler: Callable[[Message], Awaitable[None]]
    """异步处理函数"""
    event_type: PostType
    """监听的事件类型"""
    rule: Rule
    """匹配规则"""
    priority: int = 0
    """优先级 (越高越先执行)"""
    once: bool = False
    """一次性监听器"""

    __hash__ = object.__hash__

    def __repr__(self) -> str:
        handler_name = getattr(self.handler, "__name__", str(self.handler))
        return (
            f"Listener({handler_name}, "
            f"event={self.event_type.value}, "
            f"rule={self.rule!r}, "
            f"priority={self.priority}"
            f"{', once' if self.once else ''})"
        )
