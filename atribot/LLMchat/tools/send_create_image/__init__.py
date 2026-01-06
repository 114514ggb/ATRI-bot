from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.commands.bromidic.picture_processing import pictureProcessing
from atribot.core.service_container import container



tool_json = {
    "name": "send_create_image",
    "description": "这是你的画板,图像生成工具，能够根据提示词自动生成对应的图片，并自动将生成的图片发送给用户。适用于需要你绘画的场景",
    "properties": {
        "group_id": {
            "type": "string",
            "description": "要发送的当前群号",
        },
        "prompt": {
            "type": "string",
            "description": "需要生成图片的prompt,只能是英文"
        },
        "width": {
            "type": "integer",
            "description": "图像宽度，单位像素",
            "default": 1024
        },
        "height": {
            "type": "integer",
            "description": "图像高度，单位像素",
            "default": 1024
        },
    }
}

send_message:qq_send_message = container.get("SendMessage")

async def main(group_id, prompt, width="1024", height="1024"):
    """生成发送图片消息"""
    #可用模型https://image.pollinations.ai/models
    # ["flux","kontext","turbo","nanobanana"]
    
    # url = await self.model.generate_image(prompt)
    #&enhance=true
    url_base64 = await pictureProcessing.generate_image_base64(
        prompt = prompt,
        width = width,
        height = height,
        model = "nanobanana",
        timeout = 20
    )

    data = await send_message.send_group_pictures(group_id,f"base64://{url_base64}",local_Path_type=False,get_return=True)
    # print("图片发送成功")
    return {"status":f"已经尝试发送要求生成的图片,发送结果：{data}"}


