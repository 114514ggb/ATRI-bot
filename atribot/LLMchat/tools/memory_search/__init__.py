from atribot.core.service_container import container
from atribot.LLMchat.memory.memiry_system import memorySystem
import datetime




tool_json = {
    "name": "memory_search",
    "description": "基于向量相似度的检索工具，根据输入文本的语义查找相关的记忆或是知识库内容,当你想了解一个人的时候,或是想回忆起什么相关的事情时可以查询",
    "properties": {
        "user_id": {
            "type": "number",
            "description": "用于筛选user的参数,不添加默认为空,空的话查询范围包括全部用户记忆和知识库",
            "default": None
        },
        "limit":{
            "type": "number",
            "description": "返回结果的最大数量,如果结果过长会截断",
            "default": 10
        },
        "question_text": {
            "type": "string",
            "description": "查询文本，系统将基于此文本的语义向量查找相似记忆,比如你想知道一个人是谁直接输入\"是谁\"或\"称呼\"就能返回你要的相关的记忆,如果不输入此参数则返回时间降序的记忆",
            "default": None
        }
    }
}

memiry_system:memorySystem = container.get("memirySystem")

async def main(question_text:str=None,limit:int=10,user_id:str|int=None):
    if user_id:
        formatting_list = [(datetime.datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S"),r[1]) for r in await memiry_system.query_user_memory(user_id,limit, question_text)]
    else:
        formatting_list = [(datetime.datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S"),r[1] if r[1] else "知识库",r[2]) for r in await memiry_system.query_add_memory(limit, question_text)]

    
    return f"查询记忆返回值:{formatting_list}"