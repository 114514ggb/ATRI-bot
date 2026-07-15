import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from atribot.core.type.onebot_event_types import OneBotEvent


class Message:
    """消息信封

    携带:
        - event:     OneBot 事件对象
        - 时序元数据: 创建时间 / 接收时间 / 当前处理节点时间
        - 元信息:     来源平台 / 消息方向

    Usage:
        raw = {"post_type": "message", "message_type": "group", ...}
        event = OneBotEvent.from_dict(raw)
        msg = Message(event=event, source="napcat", direction="incoming")
        # ... 处理 ...
        msg.update_process_time()  # 建议在进入下一处理节点时调用
    """

    __slots__ = (
        "create_time",
        "receive_time",
        "process_time",
        "event",
        "direction",
        "source",
    )

    create_time: float
    """消息产生时间(取自 event.time,Unix 秒)"""
    receive_time: float
    """消息处理器首次接收到这次消息的时间(time.time())"""
    process_time: float
    """到达当前处理节点的时间(time.time())，每次进入新节点应调用 update_process_time()"""
    event: OneBotEvent
    """强类型的 OneBot 事件对象"""
    source: str
    """来源标识，如 'napcat'、'llonebot' 等，用于区分不同平台适配器"""

    def __init__(
        self,
        event: OneBotEvent,
        *,
        direction: str = "incoming",
        source: str = "",
    ):
        self.create_time = float(event.time)
        self.receive_time = self.process_time = time.time()
        self.event = event
        self.direction = direction
        self.source = source

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
    def group_id(self) -> Optional[int]:
        """便捷获取群号"""
        ev = self.event
        if hasattr(ev, "group_id"):
            gid = getattr(ev, "group_id")
            if isinstance(gid, int) and gid > 0:
                return gid
        return None

    @property
    def user_id(self) -> Optional[int]:
        """便捷获取用户 QQ 号"""
        ev = self.event
        if hasattr(ev, "user_id"):
            uid = getattr(ev, "user_id")
            if isinstance(uid, int) and uid > 0:
                return uid
        return None

    def __repr__(self) -> str:
        ev_type = type(self.event).__name__
        return (
            f"Message(event={ev_type}, direction={self.direction!r}, "
            f"source={self.source!r}, age={self.age_seconds:.1f}s)"
        )

    def __str__(self) -> str:
        return self.__repr__()