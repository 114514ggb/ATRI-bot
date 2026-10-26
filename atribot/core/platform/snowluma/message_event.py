from atribot.core.platform.onebot.message_event import OneBotMessageEvent
from atribot.core.platform.send_client import SendClientBase
from atribot.core.type.onebot_event_types import OneBotEvent


class SnowLumaMessageEvent(OneBotMessageEvent):
    """SnowLuma 平台的消息事件实现"""

    __slots__ = ()

    def __init__(
        self,
        event: OneBotEvent,
        *,
        send_client: SendClientBase,
        direction: str = "incoming",
        source: str = "snowluma",
    ):
        super().__init__(
            event=event,
            send_client=send_client,
            direction=direction,
            source=source,
        )
