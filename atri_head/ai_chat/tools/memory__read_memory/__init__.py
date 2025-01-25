import json

memory_path = "assets/memory.json"

tool_json = {
    "name": "memory__read_memory",
    "description": "每当你想要获取更多有关某人的信息的时候，请调用这个函数,建议聊天前记得看看哦~",
    "properties": {
        "user_id": {
            "type": "string",
            "description": "你想获取的人的user_id"
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