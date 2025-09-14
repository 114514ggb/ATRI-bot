from atribot.core.types import ToolCallsStopIteration

tool_json = {
    "name": "tool_calls_end",
    "description": "终止循环调用,适用于：1.不需要你回复 2.会话流程需保持静默,2.工具调用结束",
    "properties": None
}

async def main():
    raise ToolCallsStopIteration()


