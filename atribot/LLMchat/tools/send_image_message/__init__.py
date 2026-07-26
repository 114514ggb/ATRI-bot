from atribot.core.type.bot_types import atriMessageEvent

tool_json = {
    "name": "send_image_message",
    "description": "向群里发送一个url图像",
    "properties": {
        "url": {
            "type": "string",
            "description": "url链接",
        }
    }
}

async def main(url: str, message_data: atriMessageEvent) -> str:

    text = await message_data.send_client.send_group_pictures(
            message_data.group_id,
            url,
            local_Path_type = False,
        )

    return f"发送图像执行结果:{text}"