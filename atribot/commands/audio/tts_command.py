from pathlib import Path

from atribot.commands.audio.TTS import TTSService
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")


@cmd_system.register_command(
    name="tts",
    description="TTS文本合成语音",
    aliases=["语音合成", "说话"],
    examples=[
        "/tts 当然我是高性能的",
        "/tts --emotion 平静 --speed 1.2 好吃就是高兴嘛",
        "/tts -e 机械 -s 0.8 这是一段测试文本"
    ],
    authority_level=1
)
@cmd_system.argument(
    name="target_text",
    description="需要合成的混合文本,支持中日英韩（目前不要输入韩文）",
    required=True,
    metavar="TEXT",
    multiple=True
)
@cmd_system.option(
    name="emotion",
    short="e",
    long="emotion",
    description="音频的情感,可选值：高兴, 机械, 平静",
    default="高兴",
    choices=["高兴", "机械", "平静"],
    metavar="EMOTION"
)
@cmd_system.option(
    name="speed",
    short="s",
    long="speed",
    description="语速,取值范围0.6~1.65",
    default=1.0,
    type=float,
    metavar="SPEED"
)
async def tts_synthesis(message_data: MessageEventEnvelope, target_text: list[str], emotion: str = "高兴", speed: float = 1.0):
    """TTS文本合成语音
        
    Args:
        message_data(dict): 每个命令固定传递
        target_text (str): 需要合成的文本,支持中日英韩,但是目前不要输入韩文
        emotion (str): 音频的情感,枚举值：高兴,机械,平静
        speed (float): 语速,取值范围0.6~1.65,默认1
    """
    tts_main = TTSService()
    audio_path: Path = await tts_main.get_tts_path(
        text="".join(target_text),
        emotion=emotion,
        speed=speed
    )
    await message_data.send_client.send_group_audio(
        group_id=message_data.group_id,
        url_audio=audio_path.as_posix(),
    )
