from typing import Optional

from asyncpg import Record

from atribot.common_utils import format_memory_records, parse_time_to_timestamp
from atribot.core.service_container import container
from atribot.LLMchat.memory.memory_system import memorySystem
from atribot.LLMchat.RAG.vector_store import MemoryCategory

tool_json = {
    "name": "memory_search",
    "description": "记忆检索工具当需要回忆过去发生的事件、了解某人的特定信息、或者查询知识库中的设定时使用支持按时间范围、用户、群组、记忆类型、重要度等多维度筛选",
    "properties": {
        "question_text": {
            "type": "string",
            "description": "你要查询内容的相关文本例如：'张三喜欢什么电影'，工具会同时进行语义向量检索和全文检索并融合排序返回最相关的记忆。如果不填则按创建时间倒序返回最近的记忆",
        },
        "search_scope": {
            "type": "string",
            "enum": [
                "all",
                "user_only",
                "knowledge_base_only"
            ],
            "description": "搜索的数据范围-'all': 搜索所有内容（默认-'user_only':仅搜索用户和群组的聊天记忆，排除通用知识库-'knowledge_base_only':仅搜索预设的知识库，排除用户聊天记录",
            "default": "all"
        },
        "start_date": {
            "type": "string",
            "description": "筛选记忆的开始日期，格式必须为 'YYYY-MM-DD' (例如 '2026-01-01')如果不填则不限制开始时间",
        },
        "end_date": {
            "type": "string",
            "description": "筛选记忆的结束日期，格式必须为 'YYYY-MM-DD'如果不填则默认至今",
        },
        "user_id": {
            "type": "number",
            "description": "筛选特定用户的记忆如果想了解特定某人的信息请填入此ID",
        },
        "group_id": {
            "type": "number",
            "description": "筛选特定群组内的记忆",
        },
        "limit": {
            "type": "number",
            "description": "返回结果的最大数量",
            "default": 15,
            "minimum": 3,
            "maximum": 50
        },
        "category": {
            "type": "string",
            "enum": [
                "preference",
                "fact",
                "experience",
                "emotion",
                "group_topic",
                "knowledge",
                "domain",
                "guideline"
            ],
            "description": "筛选特定类型的记忆:preference、fact、experience、emotion、group_topic、knowledge、domain、guideline",
            "default" : "fact"
        },
        "min_importance": {
            "type": "number",
            "description": "只返回重要度大于等于此值的记忆",
            "default": 1,
            "minimum": 1,
            "maximum": 10
        },
        "min_credibility": {
            "type": "number",
            "description": "只返回可信度大于等于此值的记忆",
            "default": 1,
            "minimum": 1,
            "maximum": 10
        },
        "time_decay_weight": {
            "type": "number",
            "description": "时间衰减权重,控制越旧的记忆得分下降幅度,值越大时间对评分影响越大",
            "default": 0.3,
            "minimum": 0,
            "maximum": 2.0
        }
    },
}

memory_system: memorySystem = container.get("memorySystem")


async def main(
    question_text: Optional[str] = None,
    limit: int = 15,
    user_id: Optional[int] = None,
    group_id: Optional[int] = None,
    start_date: str = None,
    end_date: str = None,
    search_scope: str = "all",
    category: Optional[str] = None,
    min_importance: int = 1,
    min_credibility: int = 1,
    time_decay_weight: float = 0.3,
):
    """
    Args:
        question_text: 查询内容（可选，为空时按创建时间倒序返回最近记忆）
        limit: 数量限制
        user_id: 用户ID
        group_id: 群组ID
        start_date: 开始日期字符串 (YYYY-MM-DD)
        end_date: 结束日期字符串 (YYYY-MM-DD)
        search_scope: 搜索范围 enum ["all", "user_only", "knowledge_base_only"]
        category: 记忆类型筛选
        min_importance: 重要度下界 (1~10)
        min_credibility: 可信度下界 (1~10)
        time_decay_weight: 时间衰减权重,0=禁用，值越大时间影响越强
    """
    exclude_knowledge_base = False
    only_knowledge_base = False

    if search_scope == "user_only":
        exclude_knowledge_base = True
    elif search_scope == "knowledge_base_only":
        only_knowledge_base = True

    mem_category: MemoryCategory|None = category  # type: ignore[assignment]

    start_time = parse_time_to_timestamp(start_date)
    end_time = parse_time_to_timestamp(end_date, is_end_time=True)
    min_imp = min_importance if min_importance > 1 else None
    min_cred = min_credibility if min_credibility > 1 else None

    if question_text and question_text.strip():
        ret_list: list[Record] = await memory_system.hybrid_recall(
            query_text=question_text,
            limit=limit,
            user_id=user_id,
            group_id=group_id,
            start_time=start_time,
            end_time=end_time,
            exclude_knowledge_base=exclude_knowledge_base,
            only_knowledge_base=only_knowledge_base,
            category=mem_category,
            min_importance=min_importance,
            min_credibility=min_credibility,
            time_decay_weight=time_decay_weight,
            update_stats = True
        )
    else:
        ret_list: list[Record] = await memory_system.vector_store.query_memories(
            query_vector=None,
            limit=limit,
            user_id=user_id,
            group_id=group_id,
            start_time=start_time,
            end_time=end_time,
            exclude_knowledge_base=exclude_knowledge_base,
            only_knowledge_base=only_knowledge_base,
            category=mem_category,
            min_importance=min_imp,
            min_credibility=min_cred,
            update_stats = True
        )

    if ret_list:
        return f"记忆查询返回值:{format_memory_records(ret_list)}"
    else:
        return "未查询到相关记忆或知识库信息"
