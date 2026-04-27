import textwrap

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage, File, GroupMessage

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")
db: AsyncPostgreSQL = container.get("database")


@cmd_system.register_command(
    name='run',
    description='执行异步Python代码',
    examples=[
        "/run await send_message.send_group_message(984466158, 'hello')",
    ],
    authority_level=3
)
async def run_async_code(message_data: ChatMessage):
    """
    异步执行代码的测试命令
    """

    GroupMessage
    File

    raw = message_data.pure_text.strip()
    src = f"""
async def function(message_data,container):
{textwrap.indent(raw[raw.find(' ') + 1:].strip(), "  ")}
"""
    locs = {}
    exec(src, globals(), locs)
    await locs["function"](message_data, container)
