from atribot.common_utils import search_music
from atribot.core.type.bot_types import atriMessageEvent

tool_json = {
    "name": "send_cloud_music",
    "description": "分享来源网易云的歌曲,有人让你唱歌可以调用这个工具",
    "properties": {
        "name": {
            "type": "string",
            "description": "歌曲名称",
        }
    }
}


async def main(name: str, message_data: atriMessageEvent):
    """分享网易云歌曲

    Args:
        name (str): 歌曲名称
    """
    if music_lsit := await search_music(name):
        await message_data.deliver_music("163", str(music_lsit[0]["id"]))

        return f"已发送歌曲:{music_lsit[0]["name"]}"
    else:
        return "没有这首歌"
