from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.service_container import container
from atribot.common import common



tool_json = {
    "name": "send_cloud_music",
    "description": "分享来源网易云的歌曲,有人让你唱歌可以调用这个工具",
    "properties": {
        "group_id": {
            "type": "string",
            "description": "要发送的当前群号",
        },
        "name": {
            "type": "string",
            "description": "歌曲名称",
        }
    }
}


send_message:qq_send_message = container.get("SendMessage")

async def main(group_id:int|str, name:str,):
    """分享网易云歌曲

    Args:
        name (str): 歌曲名称
        group_id (int | str): 群号
    """
    
    if music_lsit := await common.search_music(name):
        await send_message.send_group_music(
            group_id,
            "163",
            str(music_lsit[0]["id"])
        )
        
        return {"send_cloud_music":f"已发送:{music_lsit[0]["name"]}<NOTICE>需要再调用tool_calls_end工具代表工具调用结束</NOTICE>"}
    else:
        return {"send_cloud_music":"没有这首歌"}

