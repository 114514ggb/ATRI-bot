from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

tool_json = {
    "name": "set_group_ban",
    "description": "尝试禁言群里的一个user,不能禁言群主或是管理员而且你必须要是群管理员才能使用",
    "properties": {
        "user_id": {
            "type": "string",
            "description": "用户的id即qq号",
        },
        "duration": {
            "type": "integer",
            "description": "禁言时间单位秒,取值范围0~2591999,0就是解禁",
        },
    }
}


send_message:QQAPIClient = container.get("SendMessage")

async def main(user_id:int, duration:int, message_data: ChatMessage):
    return (f"执行禁言返回值:{await send_message.set_group_ban(
        message_data.group_id,
        user_id,
        duration
    )}")

