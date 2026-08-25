import time

from asyncpg.exceptions import UniqueViolationError

from atribot.core.service_container import container
from atribot.LLMchat.memory.memory_system import MemorySystem
from atribot.LLMchat.RAG.vector_store import MemoryCategory

tool_json = {
    "name": "memory_storage",
    "description": "用于存储一条信息或记忆的工具,要用于存储需要长期记录的事情",
    "properties": {
        "user_id": {
            "type": "number",
            "description": "用户的唯一标识，用于关联存储的记忆,如果不提供则默认为空代表这是需要记住的概念的知识库记忆",
            "default": None
        },
        "content_text": {
            "type": "string",
            "description": "要存储的记忆内容,建议详细描述记忆的具体内容，以便后续检索时能够更准确地找到相关记忆",
        },
        "category": {
            "type": "string",
            "description": "记忆类型可选值:preference(用户偏好)、fact(事实)、experience(经历)、emotion(情感)、group_topic(群聊话题)、knowledge(通用知识)、domain(领域专业知识)、guideline(行为准则)",
            "default": "fact"
        },
        "importance": {
            "type": "number",
            "description": "记忆的重要度",
            "minimum": 1,
            "maximum": 10,
            "default": 5
        },
        "credibility": {
            "type": "number",
            "description": "记忆的可信度",
            "minimum": 1,
            "maximum": 10,
            "default": 5
        }
    }
}

memory_system: MemorySystem = container.get("MemorySystem")

async def main(
    content_text: str,
    user_id: str | int = None,
    category: MemoryCategory = "fact",
    importance: int = 5,
    credibility: int = 5,
):

    target_user_id = int(user_id) if user_id else None

    event_vector = str(await memory_system.rag.calculate_embedding(content_text))

    try:
        if target_user_id:
            await memory_system.vector_store.storage(
                group_id=None,
                user_id=target_user_id,
                event_time=int(time.time()),
                event=content_text,
                event_vector=event_vector,
                category=category,
                importance=importance,
                credibility=credibility,
            )
        else:
            await memory_system.vector_store.storage(
                group_id=None,
                user_id=None,
                event_time=int(time.time()),
                event=content_text,
                event_vector=event_vector,
                category=category,
                importance=importance,
                credibility=credibility,
            )
    except UniqueViolationError:
        prefix = f"用户:{target_user_id}," if target_user_id else "知识库,"
        return (
            f"该记忆已存在({prefix}内容与现有记忆重复)，无需重复存储。"
            f"如需修改或补充请使用对应的更新操作，避免浪费 token。"
        )

    return "存储记忆成功"