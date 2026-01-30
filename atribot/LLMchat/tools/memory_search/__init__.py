from atribot.core.service_container import container
from atribot.LLMchat.memory.memiry_system import memorySystem
import datetime




tool_json = {
    "name": "memory_search",
    "description": "基于语义的记忆检索工具。当需要回忆过去发生的事件、了解某人的特定信息、或者查询知识库中的设定时使用。支持按时间范围、用户、群组或特定范围进行筛选",
    "properties": {
        "question_text": {
            "type": "string",
            "description": "查询的核心内容。例如：'张三是谁'、'喜欢什么电影'。如果不填则按时间倒序返回最近的记忆。",
        },
        "search_scope": {
            "type": "string",
            "enum": [
                "all",
                "user_only",
                "knowledge_base_only"
            ],
            "description": "搜索的数据范围。\n- 'all': 搜索所有内容（默认）。\n- 'user_only': 仅搜索用户和群组的聊天记忆，排除通用知识库。\n- 'knowledge_base_only': 仅搜索预设的知识库/设定集，排除用户聊天记录。",
            "default": "all"
        },
        "start_date": {
            "type": "string",
            "description": "筛选记忆的开始日期，格式必须为 'YYYY-MM-DD' (例如 '2023-01-01')。如果不填则不限制开始时间。",
        },
        "end_date": {
            "type": "string",
            "description": "筛选记忆的结束日期，格式必须为 'YYYY-MM-DD'。如果不填则默认至今。",
        },
        "user_id": {
            "type": "number",
            "description": "筛选特定用户的记忆。如果想了解特定某人的信息请填入此ID。",
        },
        "group_id": {
            "type": "number",
            "description": "筛选特定群组内的记忆。",
        },
        "limit": {
            "type": "number",
            "description": "返回结果的最大数量。",
            "default": 15,
            "minimum": 1,
            "maximum": 50
        }
    },
}

memiry_system:memorySystem = container.get("memirySystem")

async def main(
    question_text: str = None,
    limit: int = 15,
    user_id: str | int = None,
    group_id: str | int = None,
    start_date: str = None,
    end_date: str = None,
    search_scope: str = "all"
):
    """
    Args:
        question_text: 查询内容
        limit: 数量限制
        user_id: 用户ID
        group_id: 群组ID
        start_date: 开始日期字符串 (YYYY-MM-DD)
        end_date: 结束日期字符串 (YYYY-MM-DD)
        search_scope: 搜索范围 enum ["all", "user_only", "knowledge_base_only"]
    """
    exclude_knowledge_base = False
    only_knowledge_base = False

    if search_scope == "user_only":
        exclude_knowledge_base = True
    elif search_scope == "knowledge_base_only":
        only_knowledge_base = True

    ret_list = await memiry_system.query_memories(
        query_text=question_text,
        limit=limit,
        user_id=user_id,
        group_id=group_id,
        start_time=parse_time_to_timestamp(start_date),
        end_time=parse_time_to_timestamp(end_date, is_end_time=True),
        exclude_knowledge_base=exclude_knowledge_base,
        only_knowledge_base=only_knowledge_base
    )

    if ret_list:
        formatted_results = []
        for r in ret_list:
            
            ts = r[3]
            time_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "未知时间"
            
            source_info = []
            if r[1]: 
                source_info.append(f"群组:{r[1]}")
            if r[2]: 
                source_info.append(f"用户:{r[2]}")
            source_str = " | ".join(source_info) if source_info else "公共信息"
            
            content = r[4]
            
            formatted_results.append(f"[{time_str}{source_str}]\n内容: {content}")

        return "查询记忆返回值:\n" + "\n\n".join(formatted_results)
    else:
        return "未查询到相关记忆或知识库信息。"


def parse_time_to_timestamp(time_str: str, is_end_time: bool = False) -> int | None:
    """
    将 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS' 转换为时间戳
    """
    if not time_str:
        return None
    
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(time_str, fmt)
            if is_end_time and fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None