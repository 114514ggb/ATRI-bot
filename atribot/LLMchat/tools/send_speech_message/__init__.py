from atribot.commands.audio.TTS import TTSService
from atribot.core.service_container import container
from atribot.core.network_connections.qq_send_message import qq_send_message



send_message:qq_send_message = container.get("SendMessage")
tts_main = TTSService()

tool_json = {
    "name": "send_speech_message",
    "description": "在你想发语音或是有人让你说话（发声的那种）的时候使用,将文本内容转换为语音消息并进行发送,要避免输入符号等不可读文本",
    "properties": {
        "group_id": {
            "type": "number",
            "description": "要发送的当前群号,必须参数",
        },
        "text": {
            "type": "string",
            "description": "需转换为语音的文本内容（支持中文/日语）可以混合语言,不要加入英文字母",
        },
        "emotion": {
            "type": "string",
            "enum": ["高兴", "机械", "平静"],
            "description": "音频的情感",
            "default": "高兴"
        },
        "speed": {
            "type": "number",
            "description": "语速,取值范围0.6~1.65",
            "default": 0.9
        }
    }
}

async def main(group_id, text, emotion="高兴", speed=0.9):
    """发送语音消息"""
    audio_path = await tts_main.get_tts_path(
        text = text,
        emotion = emotion,
        speed = speed
    )
    await send_message.send_group_audio(group_id, audio_path,default=True)

    return f"已发送语音：{text}"