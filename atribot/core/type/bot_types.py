import time
from abc import ABC
from typing import TYPE_CHECKING, Any, Generic, NotRequired, Optional, TypedDict, TypeVar

if TYPE_CHECKING:
    from atribot.core.platform.send_client import SendClientBase

from atribot.core.type.chat_message_types import SendMessage
from atribot.core.type.chat_types import GroupContext, PrivateContext
from atribot.core.type.onebot_event_types import (
    AnyMetaEvent,
    AnyNoticeEvent,
    AnyRequestEvent,
    GroupMessageEvent,
    MessageEvent,
    OneBotEvent,
    PrivateMessageEvent,
)

E = TypeVar("E", bound=OneBotEvent, default=OneBotEvent)


class atriMessageEvent(ABC, Generic[E]):
    """消息事件基类

    携带:
        - event:     OneBot 事件对象（或其他平台事件）
        - 时序元数据: 创建时间 / 接收时间 / 当前处理节点时间
        - 元信息:     来源平台

    子类职责:
        - 在 __init__ 中传入 send_client
        - 可覆写 message() 以返回预填目标 ID 的类型化消息

    Usage:
        raw = {"post_type": "message", "message_type": "group", ...}
        event = OneBotEvent.from_dict(raw)
        msg = OneBotMessageEvent(event=event, source="napcat",
                                  direction="incoming", send_client=client)
        # ... 处理 ...
        await msg.send(msg.text("hello"))
    """

    __slots__ = (
        "create_time",
        "receive_time",
        "process_time",
        "event",
        "direction",
        "source",
        "stop_propagation",
        "prevent_default",
        "_extra",
        "group_id",
        "user_id",
        "is_at",
        "send_client",
    )

    create_time: int
    """消息产生时间(取自 event.time,Unix 秒)"""
    receive_time: float
    """消息处理器首次接收到这次消息的时间(time.time())"""
    process_time: float
    """到达当前处理节点的时间(time.time())，每次进入新节点应调用 update_process_time()"""
    event: E
    """平台事件对象"""
    send_client: SendClientBase
    """发送客户端，委托发消息到平台"""
    source: str
    """来源标识，如 'napcat'、'llonebot' 等，用于区分不同平台适配器"""
    stop_propagation: bool
    """设置为 True 可中断 EventBus 后续监听器的传播"""
    prevent_default: bool
    """设置为 True 可阻止默认行为"""
    _extra: extra
    """通用上下文挂载点，供 Pipeline 中间件写入数据"""

    def __init__(
        self,
        event: E,
        *,
        send_client: SendClientBase,
        direction: str = "incoming",
        source: str = "",
    ):
        self.create_time = event.time
        self.receive_time = self.process_time = time.time()
        self.event = event
        self.send_client = send_client
        self.direction = direction
        self.source = source
        self.stop_propagation = False
        self.prevent_default = False
        self._extra = {}

        ev = self.event
        self.group_id: Optional[int] = getattr(ev, "group_id", None)
        self.user_id: Optional[int] = getattr(ev, "user_id", None)
        self.is_at: bool = getattr(ev, "is_at", False)

    def update_process_time(self) -> None:
        """更新当前处理节点时间为当前时间戳

        每个处理节点在开始处理前应调用此方法，用于追踪消息在各节点的耗时。
        当 process_time - receive_time 超过阈值时，上游可丢弃该消息避免堆积。
        """
        self.process_time = time.time()

    @property
    def age_seconds(self) -> float:
        """消息从产生到现在的总耗时(秒)"""
        return time.time() - self.create_time

    @property
    def latency_seconds(self) -> float:
        """消息从接收到现在的耗时(秒)"""
        return time.time() - self.receive_time

    @property
    def node_elapsed_seconds(self) -> float:
        """消息在当前处理节点的耗时(秒)"""
        return time.time() - self.process_time

    def is_stale(self, max_age: float = 300.0) -> bool:
        """消息是否已过期(默认超过 5 分钟视为过期)"""
        return self.age_seconds > max_age

    def is_discardable(self, max_latency: float = 60.0) -> bool:
        """消息是否应丢弃(从接收到现在超过阈值)"""
        return self.latency_seconds > max_latency

    @property
    def llm_formatted_message(self) -> str:
        """AI 可读格式化消息"""
        return self.event.llm_formatted_message

    @property
    def primeval(self) -> dict:
        """原始事件字典"""
        return self.event.primeval

    def set_extra(self, key: str, value: object) -> None:
        """在消息信封上挂载自定义上下文数据

        Pipeline 中间件可用此方法向后续处理器传递数据。
        """
        self._extra[key] = value

    def get_extra(self, key: str, default: object = None) -> object:
        """读取消息信封上的自定义上下文数据"""
        return self._extra.get(key, default)

    async def send(self, message: SendMessage) -> Any:
        """发送消息到平台

        委托给 self.send_client.send() 实现，子类一般无需覆写。

        Args:
            message: 已构建的 SendMessage 对象(GroupMessage / PrivateMessage)

        Returns:
            平台响应，具体类型由子类决定
        """
        return await self.send_client.send(message)

    def message(self) -> SendMessage:
        """创建一个空的 SendMessage 构建器

        平台子类应覆写此方法以返回预填目标 ID 的类型化消息
        （如 GroupMessage、PrivateMessage
        """
        return SendMessage()

    def text(self, text: str) -> SendMessage:
        """创建纯文本消息"""
        return self.message().add_text(text)

    def image(
        self,
        file: str,
        file_name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> SendMessage:
        """创建图片消息

        Args:
            file: 文件路径、URL、Base64 字符串
            file_name: 文件名(可选)
            summary: 图片描述(可选)
        """
        return self.message().add_image(file, file_name, summary)

    def markdown(self, text: str) -> SendMessage:
        """创建 Markdown 消息"""
        return self.message().add_markdown(text)

    def reply_text(self, text: str) -> SendMessage:
        """创建回复+文本消息（自动添加 reply 段）

        Args:
            text: 回复的文本内容
        """
        msg = self.message()
        mid = getattr(self.event, "message_id", None)
        if mid is not None:
            msg.add_reply(mid)
        msg.add_text(text)
        return msg

    def __repr__(self) -> str:
        ev_type = type(self.event).__name__
        return (
            f"atriMessageEvent(event={ev_type}, direction={self.direction!r}, "
            f"source={self.source!r}, age={self.age_seconds:.1f}s)"
        )

    def __str__(self) -> str:
        return self.__repr__()


class extra(TypedDict):
    
    group_context:NotRequired[GroupContext]
    private_context:NotRequired[PrivateContext]


MessageEventEnvelope = atriMessageEvent[MessageEvent]
"""通用消息事件信封"""
GroupMessageEnvelope = atriMessageEvent[GroupMessageEvent]
"""群聊消息事件信封"""
PrivateMessageEnvelope = atriMessageEvent[PrivateMessageEvent]
"""私聊消息事件信封"""
NoticeEnvelope = atriMessageEvent[AnyNoticeEvent]
"""通知事件信封"""
RequestEnvelope = atriMessageEvent[AnyRequestEvent]
"""请求事件信封"""
MetaEnvelope = atriMessageEvent[AnyMetaEvent]
"""元事件信封"""