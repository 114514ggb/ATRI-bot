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
    # await send_message.send_group(GroupMessage(group_id=message_data.group_id).add_text('消息'))
    # await send_message.send_group_message(984466158, '你好[CQ:image,file=file:///home/atri/py_project/ATRI-main/document/img/ATGRI_在瑶亚.gif]')
    # await send_message.send_group_message(984466158,'[CQ:json,data={ "app": "com.tencent.map"&#44; "config": { "autoSize": 1&#44; "forward": 1&#44; "height": "60"&#44; "type": "normal"&#44; "width": "666" }&#44; "desc": ""&#44; "meta": { "Location.Search": { "address": "你已被群主强奸"&#44; "enum_relation_type": 1&#44; "from": "plusPanel"&#44; "from_account": 2147483647&#44; "id": ""&#44; "lat": "1"&#44; "lng": "1"&#44; "name": "你已被群主强奸"&#44; "uint64_peer_account": "chaijun" } }&#44; "prompt": "你已被移除群聊"&#44; "ver": "1.1.2.21"&#44; "view": "LocationShare" }]')
    # await send_message.send_group(GroupMessage(group_id=message_data.group_id).add_text(str(container.get("ChatManager").get_private_context(168238719).chat_context)))
    # await send_message.send_group(GroupMessage(group_id=message_data.group_id).add_record(File.from_local_path("/home/atri/音乐/Boblues Remix.mp3")))

    raw = message_data.pure_text.strip()
    src = f"""
async def function(message_data,container):
{textwrap.indent(raw[raw.find(' ') + 1:].strip(), "  ")}
"""
    locs = {}
    exec(src, globals(), locs)
    await locs["function"](message_data, container)
