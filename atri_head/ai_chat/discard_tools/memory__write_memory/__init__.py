import json

memory_path = "assets/memory.json"

tool_json = {
    "name": "memory__write_memory",
    "description": "存储用户长期记忆的工具，当检测到用户的新特征、行为模式变化或重要事件时建议记录,也可以用于存储用一些琐事",
    "properties": {
        "memory": {
            "type": "string",
            "description": "格式：[今天日期] [分类] 具体内容，分类为habit/preference/persona/event"
        },
        "user_id": {
            "type": "string",
            "description": "对话用户的唯一标识id"
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