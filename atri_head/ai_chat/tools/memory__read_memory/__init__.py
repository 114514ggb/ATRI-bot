import json

memory_path = "assets/memory.json"

tool_json = {
    "name": "memory__read_memory",
    "description": "获取曾经你对用户行为喜好等记录的工具,建议输出前先调用这个函数,以提供更个性化的回答。",
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