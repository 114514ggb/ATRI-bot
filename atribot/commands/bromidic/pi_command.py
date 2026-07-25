from atribot.commands.bromidic.picture_processing import pictureProcessing
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.core.type.chat_message_types import ChatMessage, ImageSegment, ReplySegment

cmd_system: CommandSystem = container.get("CommandSystem")
image_processing = pictureProcessing()


@cmd_system.register_command(
    name="picture_processing",
    description="图片处理命令",
    aliases=["图片", "image", "img"],
    examples=[
        "/picture_processing 在草地上奔跑的猫咪",
        "/image 一只戴着眼镜的狐狸 [CQ:image,file=example.jpg]"
    ],
    authority_level=1
)
@cmd_system.argument(
    name="prompt",
    description="图片处理的提示词",
    required=True,
    metavar="PROMPT"
)
async def picture_processing_command(message_data: MessageEventEnvelope, prompt: str):
    """图片处理命令处理函数"""

    image_url_list = []

    def add_img(message):
        for segment in message.segments:
            if isinstance(segment, ImageSegment):
                image_url_list.append(segment.url)

    if isinstance(message_data.event.segments[0], ReplySegment):
        resp = await message_data.send_client.async_send("get_msg", {"message_id": message_data.event.segments[0].message_id})
        reply_data = resp["data"] if resp else None
        if reply_data:
            add_img(ChatMessage.from_chat_event(reply_data))

    add_img(message_data.event)

    img_base64 = await image_processing.step(image_url_list, prompt, model="gptimage")

    await message_data.send_client.send_group_pictures(message_data.group_id, f"base64://{img_base64}", local_Path_type=False, echo=False)
