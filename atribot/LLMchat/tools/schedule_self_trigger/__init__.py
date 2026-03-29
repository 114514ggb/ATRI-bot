import time
from datetime import datetime
from typing import Optional

from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.core.type.chat_message_types import ChatMessage, TextSegment
from atribot.LLMchat.chat import GroupChat

tool_json = {
    "name": "schedule_self_trigger",
    "description": (
        "定时自触发工具。可以在相对延迟或指定的目标日期时间后触发自己，并为届时的自己留下一句话（备注）"
        "触发时会以那句话作为输入启动一次新的群聊思考流程，就像是未来的自己收到了一条提醒消息"
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
            "description": "留给未来的自己的一句话，触发时这段话会作为提示输入给自己",
        },
    },
}


async def _trigger_self(group_id: int, note: str) -> None:
    """定时触发时执行的协程，构造一条合成消息并调用 GroupChat.step()"""
    config = container.get("config")
    group_chat:GroupChat = container.get("GroupChat")
    log = container.get("log")

    bot_id: int = config.account.id

    synthetic_message = ChatMessage(
        self_id=bot_id,
        user_id=bot_id,
        group_id=group_id,
        message_id=0,
        time=int(time.time()),
        raw_message=note,
        primeval={},
        llm_formatted_message=note,
        pure_text=note,
        segments=[TextSegment(note)],
        sender_info={
            "user_id": bot_id,
            "nickname": config.account.name,
            "card": "",
            "role": "member",
        },
    )

    prompt = (
        "这是你之前给自己设置的定时提醒，以下内容是那时的你留给现在的你的话，"
        "请基于这条提醒进行思考，决定是否发言或者执行某些操作："
    )

    log.info(f"定时自触发触发：群 {group_id}，备注：{note!r}")

    await group_chat.step(
        message=synthetic_message,
        prompt=prompt,
        group_id=group_id,
    )


async def main(
    note: str,
    message_data: ChatMessage,
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
        kwargs={"group_id": int(group_id), "note": str(note)},
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
