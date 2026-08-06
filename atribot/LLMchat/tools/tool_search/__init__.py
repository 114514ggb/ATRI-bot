"""tool_search 工具：搜索待发现工具并启用（抛约定错误交由 tool_calls_while 处理）"""

tool_json = {
    "name": "tool_search",
    "description": (
        "在<带发现执行工具>列表中按名称或关键词搜索尚未启用的工具，"
        "并将命中的工具临时加入本轮可用工具列表（仅本轮有效，下一轮对话自动还原）"
        "当需要完成任务但当前可用工具不足时，先调用本工具搜索并启用所需工具，"
        "然后再直接调用命中的工具"
    ),
    "properties": {
        "query": {
            "type": "string",
            "description": "要搜索的工具名、前缀或关键词",
        },
        "limit": {
            "type": "integer",
            "description": "最多返回并启用多少个工具",
            "minimum": 1,
        },
    },
}


async def main(query: str, limit: int = 1) -> str:
    """搜索待发现工具并启用

    本工具不直接执行搜索：抛出约定的 ToolSearchRequested 错误，
    由 LLMCoordinator.tool_calls_while 捕获后执行发现，并修改本轮
    request.tool_json 完成启用。

    Args:
        query: 要搜索的工具名、前缀或关键词
        limit: 最多返回并启用多少个工具

    Returns:
        不会正常返回（始终抛出 ToolSearchRequested）
    """
    from atribot.core.type.context_types import ToolSearchRequested

    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5

    raise ToolSearchRequested(query=query, limit=limit)
