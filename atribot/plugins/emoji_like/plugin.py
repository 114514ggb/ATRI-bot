from typing import TYPE_CHECKING

from atribot.core.event_bus.rule import Rule, UserRule
from atribot.core.type.bot_types import MessageEventEnvelope, NoticeEnvelope
from atribot.core.type.onebot_event_types import GroupMsgEmojiLikeEvent
from atribot.plugins.plugin import Plugin

if TYPE_CHECKING:
    from atribot.core.type.bot_types import atriMessageEvent


class EmojiLikeNoticeRule(Rule):
    """仅匹配非自身的表情回应添加通知"""

    rule_type = "emoji_like_notice"
    order = 60

    async def match(self, msg: atriMessageEvent) -> bool:
        ev = msg.event
        if not isinstance(ev, GroupMsgEmojiLikeEvent):
            return False

        if ev.user_id == ev.self_id:
            return False

        if not ev.primeval.get("is_add", True):
            return False
        return True


class EmojiLikePlugin(Plugin):

    plugin_name = "emoji_like"
    plugin_version = "1.0.0"
    plugin_description = "表情回应镜像 + 指定用户消息自动贴茶表情"
    plugin_author = "ATRI"

    _TARGET_USER_ID = 1317196420
    # _TARGET_USER_ID = 2631018780
    _TEA_EMOJI_ID_1 = 171 #茶
    _TEA_EMOJI_ID_2 = 49 #抱抱

    def __init__(self) -> None:
        super().__init__()

    @Plugin.on_notice(rule=EmojiLikeNoticeRule(), priority=0)
    async def on_emoji_like(self, event: NoticeEnvelope) -> None:
        """镜像回贴同样的表情"""
        ev: GroupMsgEmojiLikeEvent = event.event

        for like in ev.likes:
            emoji_id = like.get("emoji_id")
            if not emoji_id:
                continue

            await event.send_client.set_msg_emoji_like(
                message_id=ev.message_id,
                emoji_id=int(emoji_id),
                set=True,
            )


    @Plugin.on_message(rule=UserRule(_TARGET_USER_ID), priority=0)
    async def on_target_user_message(self, event: MessageEventEnvelope) -> None:
        await event.send_client.set_msg_emoji_like(
            message_id=event.event.message_id,
            emoji_id=self._TEA_EMOJI_ID_1,
            set=True,
        )
        await event.send_client.set_msg_emoji_like(
            message_id=event.event.message_id,
            emoji_id=self._TEA_EMOJI_ID_2,
            set=True,
        )



