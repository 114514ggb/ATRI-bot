from atribot.commands.audio.song import song
from atribot.core.atri_config import atriConfig
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")
config: atriConfig = container.get("config")
song_manager: song = song()


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
    authority_level=2
)
@cmd_system.flag('list', short='l', description='查看当前可用的歌曲列表')
@cmd_system.flag('refresh', short='r', description='刷新本地歌曲列表')
@cmd_system.flag('file', short='f', description='以文件形式发送歌曲,而不是语音')
@cmd_system.argument(
    'song_name_parts',
    description='要点播的歌曲名称',
    required=False,
    multiple=True,
    metavar='SONG_NAME'
)
async def handle_song_command(
    message_data: MessageEventEnvelope,
    list: bool,
    refresh: bool,
    file: bool,
    song_name_parts: list
):
    """
    处理所有与'song'命令相关的逻辑
    """
    group_id = message_data.group_id

    if refresh:
        song_manager.refresh()
        await message_data.send_client.send_group_msg(group_id, "✅ 歌曲列表已成功刷新！", echo=False)
        return

    if list:
        playlist_str = song_manager.get_full_playlist()
        await message_data.send_client.send_group_merge_text(
            group_id=group_id,
            message=playlist_str,
            source="查看歌单",
            
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
        await message_data.send_client.send_group_msg(group_id, help_message, echo=False)
        return

    song_name = " ".join(song_name_parts)
    song_path = song_manager.get_song_path(song_name)

    if song_path:
        if file:
            await message_data.send_client.send_group_file(
                group_id=group_id,
                url_file=(config.file_path.audio / "sing" / song_path).as_posix(),
                
            )
        else:
            await message_data.send_client.send_group_audio(
                group_id=group_id,
                url_audio=(config.file_path.audio / "sing" / song_path).as_posix(),
                
            )
    else:
        similar_songs = song_manager.find_similar_songs(song_name)
        if similar_songs:
            suggestions = "\n".join([f"  - {song_manager._remove_extension(s)}" for s in similar_songs])
            response = f"😥 未找到歌曲: '{song_name}'\n🤔 您是不是想找：\n{suggestions}"
        else:
            response = f"😥 未找到歌曲: '{song_name}',并且曲库中没有任何相似的歌曲。"
        await message_data.send_client.send_group_msg(group_id, response, echo=False)
