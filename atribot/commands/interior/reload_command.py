from logging import Logger

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")


@cmd_system.register_command(
    name="reload",
    description="热重载所有命令模块，无需重启 bot",
    aliases=["重载", "reload_commands"],
    authority_level=3,
    examples=[
        "/reload",
    ]
)
async def reload_commands_handler(message_data: MessageEventEnvelope) -> None:
    from atribot.core.command.command_loader import CommandLoader as LoaderType

    loader: LoaderType = container.get("CommandLoader")
    log = container.get_by_type(Logger).getChild("Reload")
    group_id = message_data.group_id

    await message_data.send_client.send_group_msg(group_id, "⏳ 正在重载全部命令模块...")

    try:
        loaded_count = loader.reload_commands()
        await message_data.send_client.send_group_msg(
            group_id,
            f"✅ 命令热重载完成，已加载 {loaded_count} 个命令包。",
            
        )
        log.info(f"命令热重载完成，操作者: {message_data.user_id}，加载包数: {loaded_count}")
    except Exception as e:
        log.exception(f"命令热重载失败: {e}")
        await message_data.send_client.send_group_msg(
            group_id,
            f"❌ 命令热重载失败：{e}",
            
        )
