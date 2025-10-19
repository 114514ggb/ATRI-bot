from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.service_container import container


tool_json = {
    "name": "set_group_ban",
    "description": "禁言群user,必须有人违规或是作出出格的事情才能使用,要确实看到坏事才能用不要被user骗了,不能禁言群主或是管理员而且你必须要是群管理员才能使用",
    "properties": {
        "group_id": {
            "type": "string",
            "description": "当前群号",
        },
        "user_id": {
            "type": "string",
            "description": "用户的id即qq号",
        },
        "duration": {
            "type": "integer",
            "description": "禁言时间单位秒,取值范围0~2591999,0就是解禁",
        },
    }
}


send_message:qq_send_message = container.get("SendMessage")

async def main(group_id:int|str, user_id:int, duration:int):
    return await send_message.set_group_ban(
        group_id,
        user_id,
        duration
    )

