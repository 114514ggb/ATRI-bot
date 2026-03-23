"""订阅推送命令模块

命令列表：
  /sub  <rss|bilibili> <URL/UID> [--name <名称>] [--interval <秒>]  订阅
  /unsub <ID>                                                          取消订阅
  /subs [--all]                                                        查看订阅列表
"""
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.subscription.subscription_manager import SubscriptionManager
from atribot.core.type.chat_message_type import ChatMessage

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")
sub_manager: SubscriptionManager = container.get("SubscriptionManager")



@cmd_system.register_command(
    name="sub",
    description="订阅 RSS 或 B站UP主动态，有新内容时自动推送到本群",
    aliases=["subscribe", "订阅"],
    authority_level=2,
    usage="/sub <rss|bilibili> <URL/UID> [--name <名称>] [--interval <秒>]",
    examples=[
        "/sub rss https://sspai.com/feed",
        "/sub rss https://rsshub.app/bilibili/user/video/12345678 --name 某UP视频",
        "/sub bilibili 12345678",
        "/sub bilibili 12345678 --name 某UP主 --interval 600",
    ],
)
@cmd_system.argument(
    name="sub_type",
    description="订阅类型：rss 或 bilibili",
    required=True,
    choices=["rss", "bilibili"],
)
@cmd_system.argument(
    name="source",
    description="RSS 订阅链接 或 B站 UP 主 UID",
    required=True,
)
@cmd_system.option(
    name="name",
    short="n",
    long="name",
    description="自定义显示名称（不填则自动推断）",
    required=False,
    default="",
    type=str,
)
@cmd_system.option(
    name="interval",
    short="i",
    long="interval",
    description="检查间隔秒数（默认 300，最小 60）",
    required=False,
    default=300,
    type=int,
)
async def subscribe_command(
    message_data: ChatMessage,
    sub_type: str,
    source: str,
    name: str = "",
    interval: int = 300,
) -> None:
    interval = max(60, interval)
    ok, msg = await sub_manager.subscribe(
        sub_type=sub_type,
        source_key=source,
        group_id=message_data.group_id,
        user_id=message_data.user_id,
        display_name=name,
        check_interval=interval,
    )
    await send_message.send_group_message(message_data.group_id, msg)


# ── /unsub ────────────────────────────────────────────────────────────────────

@cmd_system.register_command(
    name="unsub",
    description="取消本群的某个订阅（通过 /subs 查看订阅 ID）",
    aliases=["unsubscribe", "取消订阅"],
    authority_level=2,
    usage="/unsub <订阅ID>",
    examples=["/unsub 1", "/unsub 3"],
)
@cmd_system.argument(
    name="sub_id",
    description="要取消的订阅 ID",
    required=True,
    type=int,
)
async def unsubscribe_command(message_data: ChatMessage, sub_id: int) -> None:
    ok, msg = await sub_manager.unsubscribe(
        sub_id=sub_id,
        group_id=message_data.group_id,
    )
    await send_message.send_group_message(message_data.group_id, msg)



@cmd_system.register_command(
    name="subs",
    description="查看本群当前所有订阅",
    aliases=["订阅列表", "sublist"],
    authority_level=1,
    usage="/subs",
    examples=["/subs"],
)
async def list_subscriptions_command(message_data: ChatMessage) -> None:
    subs = await sub_manager.list_subscriptions(message_data.group_id)
    if not subs:
        await send_message.send_group_message(message_data.group_id, "本群当前没有任何订阅 👀")
        return

    lines = [f"📋 本群订阅列表（共 {len(subs)} 个）\n"]
    for s in subs:
        last = s["last_checked"]
        last_str = "从未检查" if last == 0 else _fmt_ts(last)
        src = s["source_key"]
        src_display = src if len(src) <= 60 else src[:57] + "..."
        lines.append(
            f"[{s['sub_id']}] {s['sub_type'].upper()} · {s['display_name']}\n"
            f"    来源：{src_display}\n"
            f"    间隔：{s['check_interval']}s  |  上次检查：{last_str}"
        )

    await send_message.send_group_merge_text(
        group_id=message_data.group_id,
        message="\n\n".join(lines),
        source="订阅列表",
    )


def _fmt_ts(ts: int) -> str:
    """将 Unix 时间戳格式化为可读字符串"""
    import time
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
