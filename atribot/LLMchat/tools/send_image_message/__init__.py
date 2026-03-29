from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

send_message:QQAPIClient = container.get("SendMessage")

tool_json = {
    "name": "send_image_message",
    "description": "发送一个url图像,在需要发送图像的时候使用",
    "properties": {
        "url": {
            "type": "string",
            "description": "图像的网络url链接",
        }
    }
}

async def main(url: str, message_data: ChatMessage) -> str:

    text = await send_message.send_group_pictures(
            message_data.group_id,
            url,
            local_Path_type = False,
            get_return=True
        )

    return f"发送图像执行结果:{text}"