from atribot.commands.interior.system_monitor import SystemMonitor
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")


@cmd_system.register_command(
    name='show',
    description='查看服务器的详细系统状态信息',
    aliases=['查看', 'list'],
    examples=[
        '/show all',
        '/show cpu mem'
    ]
)
@cmd_system.argument(
    'components',
    description='要查看的系统组件',
    required=True,
    multiple=True,
    choices=['all', 'sys', 'cpu', 'mem', 'disk', 'mcp', 'model', 'db', 'scheduler', 'services', 'sandbox', 'llm', 'chat']
)
async def handle_status_command(message_data: MessageEventEnvelope, components: list):
    """
    处理状态查询命令，并将结果以合并转发的形式发送。
    """
    group_id = message_data.group_id

    info_str = await SystemMonitor().view_list(components)

    if not info_str.strip():
        await message_data.send_client.send_group_msg(group_id, "ℹ️ 未生成任何信息，请检查您的输入参数。")
        return

    await message_data.send_client.send_group_merge_text(
        group_id=group_id,
        message=info_str,
        source="查看信息",
        
    )
