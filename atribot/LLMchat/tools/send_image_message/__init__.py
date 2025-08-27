from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.service_container import container
import random


tool_json = {
    "name": "send_image_message",
    "description": "这是你的画板,图像生成工具，能够根据提示词自动生成对应的图片，并将生成的图片发送给用户。适用于需要你绘画的场景。",
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
            "type": "string",
            "description": "图像宽度，单位像素,默认1024"
        },
        "height": {
            "type": "string",
            "description": "图像高度，单位像素,默认1024"
        },
    }
}

send_message:qq_send_message = container.get("SendMessage")

async def main(group_id, prompt, width="1024", height="1024"):
    """生成发送图片消息"""
    model = "gptimage" #flux,kontext,turbo,gptimage
    Token = "56zs_9uGTfe19hUH"
    Seed = random.randint(1, 65535)
    
    # url = await self.model.generate_image(prompt)
    #&enhance=true
    url = f"https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&private=true&Seed={Seed}&Model={model}&Token={Token}"

    data = await send_message.send_group_pictures(group_id,url,local_Path_type=False,get_return=True)
    # print("图片发送成功")
    return {"send_image_message": {"status":f"{data}<NOTICE>需要再调用tool_calls_end工具代表工具调用结束</NOTICE>"}}
