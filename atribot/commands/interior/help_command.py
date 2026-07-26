from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")


@cmd_system.register_command(
    name="help",
    description="显示帮助信息",
    aliases=["帮助"],
    examples=[
        "/help",
        "/help -l",
        "/help --list",
        "/help <命令名>"
    ],
    authority_level=0
)
@cmd_system.flag(
    name="list",
    short="l",
    long="--list",
    description="显示支持的所有命令"
)
@cmd_system.argument(
    name="command_name",
    description="要查看帮助的特定命令名",
    required=False,
    type=str
)
async def help_command(message_data: MessageEventEnvelope, command_name: str = None, list: bool = False):
    """
    显示帮助信息
    
    参数:
        message_data: 固定参数
        command_name: 要查看的特定命令
        list: 是否显示完整帮助(FLAG参数)
    """
    if list:
        help_text = cmd_system.get_help_text()
        await message_data.send_client.send_group_merge_text(
            group_id=message_data.group_id,
            message=help_text,
            source="命令list",
            
        )
    elif command_name:
        help_text = cmd_system.get_help_text(command_name)
        await message_data.send_client.send_group_merge_text(
            group_id=message_data.group_id,
            message=help_text,
            source=f"命令{command_name}帮助",
            
        )
    else:
        basic_help = (
            "ATRIbot,版本 2.0.0.1 2025.08.28\n"
            "所有命令以开头要@bot再以\"/\"开头才能使用\n"
            "输入 /help --list 查看完整命令列表\n"
            "输入 /help <命令名> 查看特定命令帮助\n\n"
            "任意命令加入 --help 参数可以查看该命令的帮助信息\n\n"
            "基本功能:\n"
            "1.@bot后接文字就可以聊天\n"
            "2.@bot后以/开头接[命令]即可触发命令.\n"
            "3.会对群出现的一些词进行反应。\n"
            "4.会对交互数据进行存储，可能会对其用于分析，服务质量优化和功能迭代。\n"
        )
        await message_data.send_client.send_group_msg(message_data.group_id, basic_help)
