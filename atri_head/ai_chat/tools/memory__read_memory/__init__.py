import json

memory_path = "assets/memory.json"

tool_json = {
    "name": "memory__read_memory",
    "description": "获取一个用户完整记忆工具,返回对一个人的全部记忆,建议在需要用户历史习惯、偏好或重要事件信息时优先调用",
    "properties": {
        "user_id": {
            "type": "string",
            "description": "对应的用户的id"
        }
    }
}

async def main(user_id: str):
    return {"memory__read_memory": read_memory(user_id)}

def read_memory(user_id: str):
    with open(memory_path, "r", encoding="utf-8") as f:
        memory_data = json.load(f)
    memorys = memory_data.get(user_id, [])
    if not memorys:
        return "好像对ta还没有任何记忆呢~"

    return f"这些是有关{user_id}的记忆：" + "\n".join(memorys)