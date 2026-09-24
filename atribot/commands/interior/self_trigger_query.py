import time
from typing import Any

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.LLMchat.tools.schedule_self_trigger.trigger_scheduler import (
    SelfTriggerScheduler,
    format_remaining,
)

cmd_system: CommandSystem = container.get("CommandSystem")


def _format_pending(item: dict[str, Any]) -> list[str]:
    """把一条待触发任务格式化为输出行"""
    target = f"群 {item['group_id']}" if item["group_id"] else f"私聊(用户 {item['user_id']})"
    trigger_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["trigger_at"]))
    note: str = item["note"]
    note = note[:100] + "..."
    
    return [
        f"\n[任务 {item['record_id'][:8]}]",
        f"🎯 目标: {target}",
        f"⏰ 触发时刻: {trigger_time} (剩余 {format_remaining(item['remaining_seconds'])})",
        f"📝 备注: {note}",
    ]


@cmd_system.register_command(
    name="trigger",
    description="查询持久化定时自触发任务",
    aliases=["定时"],
    authority_level=2,
    usage="/trigger list",
    examples=["/trigger list"],
)
@cmd_system.argument(
    name="action",
    description="子命令，当前仅支持 list",
    required=True,
    choices=["list"],
    metavar="ACTION",
)
async def cmd_self_trigger(
    action: str,
    message_data: MessageEventEnvelope,
) -> None:
    """查询持久化定时自触发任务"""
    scheduler = container.get_by_type(SelfTriggerScheduler)
    pending = scheduler.list_pending()

    if not pending:
        await message_data.send(message_data.reply_text("当前没有持久化自触发任务。"))
        return

    lines: list[str] = [f"⏱️ 持久化自触发任务 共 {len(pending)} 条", "=" * 10]
    for item in pending:
        lines.extend(_format_pending(item))
    lines.append("=" * 10)

    await message_data.send(message_data.reply_text("\n".join(lines)))
