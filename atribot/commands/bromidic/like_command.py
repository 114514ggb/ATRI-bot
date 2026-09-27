from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")

DEFAULT_LIKE_TIMES = 10
MAX_LIKE_TIMES = 20


@cmd_system.register_command(
    name="like",
    description="给指定用户点赞",
    aliases=["点赞", "send_like"],
    examples=["/点赞", "/点赞 12345", "/点赞 12345 5"],
    authority_level=1,
)
@cmd_system.argument(
    name="qq_id",
    description="目标用户 QQ 号（留空则给自己点赞）",
    required=False,
    metavar="QQ",
    type=int,
)
@cmd_system.argument(
    name="times",
    description=f"点赞次数（超出 {MAX_LIKE_TIMES} 自动截断到 {MAX_LIKE_TIMES}）",
    required=False,
    metavar="TIMES",
    type=int,
)
async def like_command(
    message_data: MessageEventEnvelope,
    qq_id: int | None = None,
    times: int | None = None,
) -> None:
    target_id = qq_id or message_data.user_id
    requested = times if times is not None else DEFAULT_LIKE_TIMES
    count = max(1, min(requested, MAX_LIKE_TIMES))

    resp = await message_data.send_client.send_like(target_id, count)

    if resp is None:
        text = "点赞请求发送失败，没有收到响应，请稍后再试"
    elif resp.get("status") == "ok" or resp.get("retcode") == 0:
        who = "你" if target_id == message_data.user_id else f"QQ {target_id}"
        text = f"已给{who}点赞 {count} 次！"
        if count != requested:
            text += f"（请求的 {requested} 次已自动调整为 {count} 次）"
    else:
        reason = (
            resp.get("wording")
            or resp.get("message")
            or f"未知错误(retcode={resp.get('retcode')})"
        )
        text = f"❌ {reason}"

    await message_data.send(message_data.reply_text(text))
