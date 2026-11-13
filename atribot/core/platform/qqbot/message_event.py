from atribot.core.platform.send_client import SendClientBase
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage
from atribot.core.type.onebot_event_types import OneBotEvent


class QQBotMessageEvent(atriMessageEvent):
    """QQ 官方机器人的消息事件信封"""

    __slots__ = ()

    def __init__(
        self,
        event: OneBotEvent,
        *,
        send_client: SendClientBase,
        direction: str = "incoming",
        source: str = "qqbot",
    ):
        super().__init__(
            event=event,
            send_client=send_client,
            direction=direction,
            source=source,
        )

    def message(self) -> SendMessage:
        """创建预填目标 ID 的类型化消息"""
        if self.group_id:
            return GroupMessage(group_id=self.group_id)
        if self.user_id:
            return PrivateMessage(user_id=self.user_id)
        return SendMessage()
