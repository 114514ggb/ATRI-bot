from atribot.core.service_container import container
from atribot.LLMchat.memory.memiry_system import memorySystem
import time





tool_json = {
    "name": "memory_storage",
    "description": "用于存储记忆的工具,推荐只记忆重要的事情,可以将一句话存储为可以被memory_search工具检索到的长期的记忆,还可以关联到特定的用户",
    "properties": {
        "user_id": {
            "type": "number",
            "description": "用户的唯一标识，用于关联存储的记忆,如果不提供则默认为空，代表这是一条知识库记忆",
            "default": None
        },
        "content_text": {
            "type": "string",
            "description": "要存储的记忆内容,建议详细描述记忆的具体内容，以便后续检索时能够更准确地找到相关记忆",
        }
    }
}

memiry_system:memorySystem = container.get("memirySystem")

async def main(content_text:str,user_id:str|int=None):
    if user_id:
        args_list = [
            (0, user_id, int(time.time()), 
             content_text, str((await memiry_system.rag.calculate_embedding(content_text))[0]))
        ]
    else:
        args_list = [
            (None, None, int(time.time()), 
             content_text, str((await memiry_system.rag.calculate_embedding(content_text))[0]))
        ]

    await memiry_system.vector_store.batch_add_memories(args_list)
    
    return "存储记忆成功"