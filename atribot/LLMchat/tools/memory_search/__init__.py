from atribot.core.service_container import container
from atribot.LLMchat.memory.memiry_system import memorySystem
import datetime




tool_json = {
    "name": "memory_search",
    "description": "基于向量相似度的检索工具，根据输入文本的语义查找相关的记忆或是知识库内容",
    "properties": {
        "user_id": {
            "type": "number",
            "description": "用于筛选user的参数,不添加默认为空，查询用户记忆和知识库",
            "default": None
        },
        "limit":{
            "type": "number",
            "description": "返回结果的最大数量,如果结果过长会截断",
            "default": 5
        },
        "question_text": {
            "type": "string",
            "description": "查询文本，系统将基于此文本的语义向量查找相似记忆",
        },
    }
}

memiry_system:memorySystem = container.get("memirySystem")

async def main(question_text:str,limit:int=5,user_id:str|int=None):
    if user_id:
        return_list = await memiry_system.query_user_memory(question_text,user_id,limit)
        return [(datetime.datetime.fromtimestamp(r[0]),r[1]) for r in return_list]
    else:
        return_list = await memiry_system.query_add_memory(question_text,limit)
        return [(datetime.datetime.fromtimestamp(r[0]),r[1] if r[1] else "知识库",r[2]) for r in return_list]
        