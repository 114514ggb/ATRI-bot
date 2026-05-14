import traceback
from logging import Logger

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.LLMchat.token_manage import TokenManager

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")
log:Logger = container.get("log")
token_manager:TokenManager = container.get("TokenManager")


@cmd_system.register_command(
    name="token",
    description="查询当前所在群或个人的详细 Token 消耗统计",
    authority_level=1,
    aliases=["tokens"],
    examples=["/token", "/token --group 123456", "/token --user 123456"]
)
@cmd_system.option(name="group", short="g", long="--group", description="查询指定群内汇总记录", type=int, required=False)
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

        stats = await token_manager.get_token_statistics(user_id=target_user, group_id=target_group)
        period_stats = await token_manager.get_period_token_statistics(user_id=target_user, group_id=target_group, days=30)
        model_stats = await token_manager.get_model_token_breakdown(user_id=target_user, group_id=target_group, days=7)

        total_prompt = stats.get('prompt_tokens', 0)
        total_completion = stats.get('completion_tokens', 0)
        total = stats.get('total_tokens', 0)

        p_prompt = period_stats.get('prompt_tokens', 0)
        p_completion = period_stats.get('completion_tokens', 0)
        p_total = period_stats.get('total_tokens', 0)

        reply = f"📊 {target_name} 的Token消耗统计:\n"
        reply += "[历史总计]\n"
        reply += f"输入消耗 (Prompt): {total_prompt}\n"
        reply += f"输出消耗 (Completion): {total_completion}\n"
        reply += f"总计: {total} Tokens\n\n"
        
        reply += "[近30天消耗]\n"
        reply += f"输入消耗 (Prompt): {p_prompt}\n"
        reply += f"输出消耗 (Completion): {p_completion}\n"
        reply += f"总计: {p_total} Tokens\n\n"

        if model_stats:
            reply += "[近7天模型消耗分布]\n"
            for row in model_stats:
                reply += f"- {row['model']}: {row['model_total']} Tokens\n"
        else:
            reply += "[近7天模型消耗分布]\n- 无记录"

        if message_data.group_id:
            await send_message.send_group_merge_forward(
                message_data.group_id,
                reply,
                source= "查询token统计"
            )

    except Exception as e:
        log.error(f"查询Token消耗失败: {e}\n{traceback.format_exc()}")
