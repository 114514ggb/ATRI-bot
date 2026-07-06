import traceback
from logging import Logger

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.LLMchat.token_manage import TokenManager

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")
log: Logger = container.get_by_type(Logger).getChild("TokenCmd")
token_manager:TokenManager = container.get("TokenManager")

PERIOD_DAYS = 30
MODEL_BREAKDOWN_DAYS = 7
MAX_MODEL_ROWS = 8


def format_token_count(value: int | None) -> str:
    return f"{int(value or 0):,}"


@cmd_system.register_command(
    name="token",
    description="查询当前所在群或个人的近期 Token 消耗统计",
    authority_level=1,
    aliases=["tokens"],
    examples=["/token", "/token --group 123456", "/token --user 123456"]
)
@cmd_system.option(name="group", short="g", long="--group", description="查询指定群内近期汇总记录", type=int, required=False)
@cmd_system.option(name="user", short="u", long="--user", description="查询指定用户记录", type=int, required=False)
async def main(message_data: ChatMessage, group: int | None, user: int | None) -> None:
    try:
        target_group = None
        target_user = None
        target_name = ""

        if group is not None:
            target_group = group
            target_name = f"群({group})"
        elif user is not None:
            target_user = user
            target_name = f"用户({user})"
        else:
            target_user = message_data.user_id
            target_name = f"用户({message_data.user_id})"

        period_stats = await token_manager.get_period_token_statistics(
            user_id=target_user,
            group_id=target_group,
            days=PERIOD_DAYS,
        )
        model_stats = await token_manager.get_model_token_breakdown(
            user_id=target_user,
            group_id=target_group,
            days=MODEL_BREAKDOWN_DAYS,
        )

        period_total = period_stats.get('total_tokens', 0)
        model_total = sum(row['model_total'] or 0 for row in model_stats)

        reply_lines = [
            "📊 Token 消耗统计",
            f"对象：{target_name}",
            "",
            f"[最近 {PERIOD_DAYS} 天汇总]",
            f"输入：{format_token_count(period_stats.get('prompt_tokens', 0))} Tokens",
            f"输出：{format_token_count(period_stats.get('completion_tokens', 0))} Tokens",
            f"合计：{format_token_count(period_total)} Tokens",
            "",
            f"[最近 {MODEL_BREAKDOWN_DAYS} 天模型分布]",
        ]

        if model_stats:
            for row in model_stats[:MAX_MODEL_ROWS]:
                row_total = row['model_total'] or 0
                percent = row_total / model_total * 100 if model_total else 0
                reply_lines.append(
                    f"- {row['model']}:{format_token_count(row_total)} Tokens({percent:.1f}%)"
                )

            hidden_count = len(model_stats) - MAX_MODEL_ROWS
            if hidden_count > 0:
                reply_lines.append(f"- 其余 {hidden_count} 个模型未展示")
        else:
            reply_lines.append("- 暂无记录")

        reply = "\n".join(reply_lines)

        if message_data.group_id:
            await send_message.send_group_merge_text(
                message_data.group_id,
                reply,
                source= "查询token统计"
            )

    except Exception as e:
        log.error(f"查询Token消耗失败: {e}\n{traceback.format_exc()}")
