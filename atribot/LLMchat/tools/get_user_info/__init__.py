from atribot.core.service_container import container
from atribot.LLMchat.memory.user_info_system import UserSystem





tool_json = {
    "name": "get_user_info",
    "description": "用于获取用户的user_info文档,里面包含一些基本信息,如果没有记录的话会返回默认文档",
    "properties": {
        "user_id": {
            "type": "number",
            "description": "用户的唯一标识,qq号",
        }
    }
}

user_system:UserSystem = container.get("UserSystem")

async def main(user_id:int):
    return f"用户info的JSON文档:{
        await user_system.get_user_info(user_id)
    }"