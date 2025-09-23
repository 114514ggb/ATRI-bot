from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.command.command_parsing import command_system
from atribot.core.service_container import container
from atribot.commands.audio.TTS import TTSService
from atribot.commands.audio.song import song


cmd_system:command_system = container.get("CommandSystem")
send_message:qq_send_message = container.get("SendMessage")
config = container.get("config")
song_manager:song = song()


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
    description="需要合成的混合文本，支持中日英韩（目前不要输入韩文）",
    required=True,
    metavar="TEXT",
    multiple=True
)
@cmd_system.option(
    name="emotion",
    short="e",
    long="emotion",
    description="音频的情感，可选值：高兴, 机械, 平静",
    default="高兴",
    choices=["高兴", "机械", "平静"],
    metavar="EMOTION"
)
@cmd_system.option(
    name="speed",
    short="s",
    long="speed",
    description="语速，取值范围0.6~1.65",
    default=1.0,
    type=float,
    metavar="SPEED"
)
async def tts_synthesis(message_data: dict, target_text:list[str], emotion:str = "高兴", speed:float = 1.0):
    """TTS文本合成语音
        
    Args:
        message_data(dict): 每个命令固定传递
        target_text (str): 需要合成的文本,支持中日英韩，但是目前不要输入韩文
        emotion (str): 音频的情感,枚举值：高兴,机械,平静
        speed (float): 语速，取值范围0.6~1.65,默认1
    """
    tts_main = TTSService()
    audio_path = await tts_main.get_tts_path(
        text= "".join(target_text),
        emotion= emotion,
        speed= speed
    )
    await send_message.send_group_audio(
        group_id = message_data["group_id"],
        url_audio = audio_path,
        default = True
    )
    
    




@cmd_system.register_command(
    name='song',
    description='点歌、查看歌单或刷新歌曲列表',
    aliases=['点歌'],
    examples=[
        '/song 新宝岛',
        '/song --list',
        '/song --refresh',
        '/song Lemon --file'
    ],
    authority_level = 2
)
@cmd_system.flag('list', short='l', description='查看当前可用的歌曲列表')
@cmd_system.flag('refresh', short='r', description='刷新本地歌曲列表')
@cmd_system.flag('file', short='f', description='以文件形式发送歌曲，而不是语音')
@cmd_system.argument(
    'song_name_parts',
    description='要点播的歌曲名称',
    required=False,
    multiple=True,
    metavar='SONG_NAME'
)
async def handle_song_command(
    message_data: dict,
    list: bool,
    refresh: bool,
    file: bool,
    song_name_parts: list
):
    """
    处理所有与'song'命令相关的逻辑
    """
    group_id = message_data.get('group_id')

    if refresh:
        song_manager.refresh()
        await send_message.send_group_message(group_id, "✅ 歌曲列表已成功刷新！")
        return

    if list:
        playlist_str = song_manager.get_full_playlist()
        await send_message.send_group_merge_text(
            group_id, 
            playlist_str,
            source = "查看歌单"
        )
        return

    if not song_name_parts:
        command = cmd_system.command_registry['song']
        usage_string = command.get_usage_string()
        help_message = (
            f"🎶 点歌姬已就绪 🎶\n"
            f"用法: {usage_string}\n"
            f"示例:\n"
            f"  /song 喀秋莎  (播放歌曲)\n"
            f"  /song --list  (查看歌单)\n"
            f"  /song --refresh  (刷新歌单)\n"
            f"  /song unravel --file (以文件发送)"
        )
        await send_message.send_group_message(group_id, help_message)
        return

    song_name = " ".join(song_name_parts)
    song_path = song_manager.get_song_path(song_name)

    if song_path:
        if file:
            await send_message.send_group_file(
                group_id, 
                config.file_path.item_path + song_path
            )
        else:
            await send_message.send_group_audio(
                group_id, 
                config.file_path.item_path + song_path
            )
    else:
        similar_songs = song_manager.find_similar_songs(song_name)
        if similar_songs:
            suggestions = "\n".join([f"  - {song_manager._remove_extension(s)}" for s in similar_songs])
            response = f"😥 未找到歌曲: '{song_name}'\n🤔 您是不是想找：\n{suggestions}"
        else:
            response = f"😥 未找到歌曲: '{song_name}'，并且曲库中没有任何相似的歌曲。"
        await send_message.send_group_message(group_id, response)