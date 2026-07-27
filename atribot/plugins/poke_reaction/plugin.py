import random

from atribot.core.type.bot_types import NoticeEnvelope
from atribot.core.type.onebot_event_types import GroupPokeEvent, PokeEvent
from atribot.plugins.plugin import Plugin
from atribot.plugins.poke_reaction.reactivity_list import reactivity_list


class PokeReactionPlugin(Plugin):
    """戳一戳反馈插件

    当有人戳机器人时，随机发送一句回应文本，并回戳对方。
    同时支持群聊和私聊场景。
    """

    plugin_name = "poke_reaction"
    plugin_version = "1.0.0"
    plugin_description = "戳一戳自动回复与回戳"
    plugin_author = "ATRI"

    @Plugin.on_notice(priority=0)
    async def on_poke(self, event: NoticeEnvelope) -> None:
        """处理戳一戳通知事件"""
        ev = event.event

        if not isinstance(ev, PokeEvent):
            return

        if ev.target_id != ev.self_id:
            return

        text = random.choice(reactivity_list)

        if isinstance(ev, GroupPokeEvent):
            await event.send_client.send_group_msg(ev.group_id, text)
            await event.send_client.send_group_poke(ev.group_id, ev.user_id)
        else:
            await event.send_client.send_private_msg(ev.user_id, text)
