from atribot.core.service_container import container
from atribot.core.network_connections.qq_send_message import qq_send_message



send_message:qq_send_message = container.get("SendMessage")

tool_json = {
    "name": "send_image_message",
    "description": "向群里发送一个url图像",
    "properties": {
        "group_id": {
            "type": "string",
            "description": "要发送的当前群号",
        },
        "url": {
            "type": "string",
            "description": "图像的网络url链接",
        }
    }
}

async def main(group_id, url):

    text = await send_message.send_group_pictures(
            group_id, 
            url,
            local_Path_type = False,
            get_return=True
        )

    return f"发送图像执行结果:{text}"