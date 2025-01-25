import json

memory_path = "assets/memory.json"

tool_json = {
    "name": "memory__write_memory",
    "description": "如果在上下中你看见并觉得应该记住的人的行为与事件，请调用这个函数，并将记忆内容写入。请尽量每次都调用，总结ta的习惯、爱好和性格,以及你对ta的印象",
    "properties": {
        "memory": {
            "type": "string",
            "description": "你想记住的内容，概括并保留关键内容,不用带user_id"
        },
        "user_id": {
            "type": "string",
            "description": "你想记住的人的user_id"
        }
    }
}

async def main(memory: str, user_id: str):
    return {"memory__write_memory":write_memory(memory, user_id)}

def write_memory(memory: str, user_id: str):

    with open(memory_path, "r", encoding="utf-8") as f:
        memory_data = json.load(f)

    memorys = memory_data.get(user_id, [])
    memorys.append(memory)
    memory_data[user_id] = memorys

    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=4)

    return "记忆已经保存啦~"