from atribot.commands.interior.query_statistics import UserActivityAnalyzer
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

cmd_system: CommandSystem = container.get("CommandSystem")


@cmd_system.register_command(
    name="psql",
    description="查询数据库并生成用户活跃度报告",
    aliases=["查询", "postgresql"],
    examples=[
        "/postgresql 2631018780",
        "/psql",
    ]
)
@cmd_system.argument(
    name="user_id",
    description="要查询的用户ID,qq号,如果没有就会查询命令的执行者",
    required=False,
    type=int
)
async def query_database_command(message_data: ChatMessage, user_id: int = 0):
    """
    查询数据库并生成用户活跃度报告
    
    参数:
        message_data: 所有命令固定传入参数
        user_id: 要查询的用户ID，如果没有就会查询命令的执行者
    """
    analyzer = UserActivityAnalyzer()
    await analyzer.query_mysql(message_data=message_data, user_id=user_id)
