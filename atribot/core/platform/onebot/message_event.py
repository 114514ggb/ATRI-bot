
from atribot.core.platform.send_client import SendClientBase
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage
from atribot.core.type.onebot_event_types import OneBotEvent


class OneBotMessageEvent(atriMessageEvent):
    """OneBot 平台的消息事件实现"""

    __slots__ = ()

    def __init__(
        self,
        event: OneBotEvent,
        *,
        send_client: SendClientBase,
        direction: str = "incoming",
        source: str = "napcat",
    ):
        super().__init__(event=event, send_client=send_client, direction=direction, source=source)

    def message(self) -> SendMessage:
        """创建预填目标 ID 的类型化消息

        - 群聊消息 → GroupMessage(group_id=...)
        - 私聊消息 → PrivateMessage(user_id=...)
        - 其他     → 普通 SendMessage
        """
        if self.group_id:
            return GroupMessage(group_id=self.group_id)
        elif self.user_id:
            return PrivateMessage(user_id=self.user_id)
        return SendMessage()
