from datetime import datetime
from typing import Optional

from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.chat import GroupChat

tool_json = {
    "name": "schedule_self_trigger",
    "description": (
        "定时自触发工具。可以在相对延迟或指定的目标日期时间后触发自己，并为届时的自己留下任务介绍，"
        "触发时会以那句话作为输入启动一次新的群聊思考流程"
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


async def _trigger_self(
    note: str,
    message_data:atriMessageEvent
    ) -> None:
    """定时触发时执行的协程"""
    group_chat = container.get_by_type(GroupChat)
    await group_chat.trigger_internal_thought(
        custom_prompt=note,
        event=message_data
    )


async def main(
    note: str,
    message_data: atriMessageEvent,
    target_datetime: Optional[str] = None,
    hours: float = 0,
    minutes: float = 0,
    seconds: float = 0,
) -> str:
    trigger: TimeTriggerSupervisor = container.get("TimeTriggerSupervisor")
    group_id = message_data.group_id

    if target_datetime:
        try:
            target_dt = datetime.strptime(target_datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return f"错误:target_datetime 格式不正确，应为 'YYYY-MM-DD HH:MM:SS'，收到：{target_datetime!r}"
        total_seconds = (target_dt - datetime.now()).total_seconds()
        if total_seconds < 10:
            return f"错误：目标时刻 {target_datetime} 距现在不足 10 秒或已在过去，无法设置。"
    else:
        total_seconds = max(float(hours) * 3600 + float(minutes) * 60 + float(seconds), 10.0)

    task_id = trigger.add_task(
        func=_trigger_self,
        trigger_delta=total_seconds,
        timeout=120.0,
        kwargs={ 
            "note": note,
            "message_data":message_data,
        },
        remarks=f"自触发 群{group_id}",
    )

    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = int(total_seconds % 60)
    time_str = "".join([
        f"{h} 小时" if h else "",
        f"{m} 分钟" if m else "",
        f"{s} 秒" if s else "",
    ]) or f"{total_seconds:.0f} 秒"
    return (
        f"已设置定时自触发(task_id={task_id})：将在 {time_str}后"
        f"在群 {group_id} 触发自己，备注内容：\"{note}\""
    )
