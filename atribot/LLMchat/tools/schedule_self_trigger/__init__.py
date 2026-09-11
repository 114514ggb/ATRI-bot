from datetime import datetime
from typing import Optional
from uuid import uuid4

from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.tools.schedule_self_trigger.trigger_scheduler import (
    DEFAULT_TASK_TIMEOUT,
    ScheduledTrigger,
    format_remaining,
    get_scheduler,
)

MIN_DELAY_SECONDS = 10.0
"""允许设置的最早触发延迟(秒), 过近的目标时刻直接拒绝"""

tool_json = {
    "name": "schedule_self_trigger",
    "description": (
        "定时自触发工具。可以在相对延迟或指定的目标日期时间后触发自己，并为届时的自己留下任务介绍，"
        "触发时会以那句话作为输入启动一次新的聊天思考流程"
    ),
    "properties": {
        "target_datetime": {
            "type": "string",
            "description": "目标触发时刻，格式为'YYYY-MM-DD HH:MM:SS'与相对延迟参数互斥，优先级更高",
        },
        "hours": {
            "type": "number",
            "description": "相对延迟的小时数",
            "default": 0,
            "minimum": 0,
        },
        "minutes": {
            "type": "number",
            "description": "相对延迟的分钟数",
            "default": 0,
            "minimum": 0,
        },
        "seconds": {
            "type": "number",
            "description": "相对延迟的秒数",
            "default": 0,
            "minimum": 0,
        },
        "note": {
            "type": "string",
            "description": "详细描述要要执行事情的情况",
        },
    },
}


async def main(
    note: str,
    message_data: atriMessageEvent,
    target_datetime: Optional[str] = None,
    hours: float = 0,
    minutes: float = 0,
    seconds: float = 0,
) -> str:
    group_id = message_data.group_id
    user_id = message_data.user_id

    if not note or not note.strip():
        return "错误:note 不能为空，请描述要执行的事情。"

    now = datetime.now().timestamp()
    if target_datetime:
        try:
            trigger_at = datetime.strptime(target_datetime, "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            return f"错误:target_datetime 格式不正确，应为 'YYYY-MM-DD HH:MM:SS'，收到：{target_datetime!r}"
        if trigger_at - now < MIN_DELAY_SECONDS:
            return f"错误：目标时刻 {target_datetime} 距现在不足 {MIN_DELAY_SECONDS:.0f} 秒或已在过去，无法设置。"
    else:
        delay = max(float(hours) * 3600 + float(minutes) * 60 + float(seconds), MIN_DELAY_SECONDS)
        trigger_at = now + delay

    record = ScheduledTrigger(
        record_id=uuid4().hex,
        note=note,
        trigger_at=trigger_at,
        created_at=now,
        source=message_data.source,
        group_id=group_id,
        user_id=user_id,
        timeout=DEFAULT_TASK_TIMEOUT,
        primeval=message_data.primeval,
    )

    try:
        record_id = await get_scheduler().schedule(record)
    except ValueError as e:
        return f"错误:{e}"

    time_str = format_remaining(trigger_at - now)
    target_str = f"群 {group_id}" if group_id else f"私聊(用户 {user_id})"
    return (
        f"已设置定时自触发(任务 {record_id[:8]})：将在 {time_str}后"
        f"在 {target_str} 触发自己，备注内容：\"{note}\"。"
        f"任务已持久化，Bot 重启后仍会生效。"
    )


get_scheduler()
