from logging import Logger
from typing import Set

from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.onebot_event_types import (
    GroupMessageEvent,
    MessageEvent,
    MessageSentEvent,
    PostType,
)

log = container.get_by_type(Logger).getChild("MessageStore")
"""模块级日志器"""

_seen_groups: Set[int] = set()
"""已处理过的群 ID 集合"""


async def store_message_to_db(msg: atriMessageEvent) -> None:
    """将消息持久化到数据库

    存储内容：
    - 首次见到的群 → 记录群信息
    - 发送者用户信息
    - 消息内容

    Args:
        msg: 待存储的消息事件
    """
    if msg.event.post_type not in (PostType.MESSAGE, PostType.MESSAGE_SENT):
        return

    group_id = msg.group_id
    ev:MessageEvent = msg.event

    if group_id and group_id not in _seen_groups:
        _seen_groups.add(group_id)
        try:
            if isinstance(ev, (GroupMessageEvent, MessageSentEvent)):
                group_name = ev.primeval.get("group_name", "")
            else:
                group_name = "[unknown]"

            async with container.get_by_type(AsyncPostgreSQL) as db:
                await db.add_group(group_id=group_id, group_name=group_name)
        except Exception as e:
            log.warning("群信息存储失败: group=%s, error=%s", group_id, e)
            return

    try:
        async with container.get_by_type(AsyncPostgreSQL) as db:
            await db.add_user(
                user_id=msg.user_id, 
                nickname=ev.sender['nickname']
            )
            await db.add_message(
                message_id=ev.message_id,
                user_id=msg.user_id,
                group_id=group_id,
                timestamp=ev.time,
                content=ev.cq_code,
            )
    except Exception as e:
        log.warning("数据存储失败: %s", e)
