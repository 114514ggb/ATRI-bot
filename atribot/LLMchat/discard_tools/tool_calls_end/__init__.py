from atribot.core.types import ToolCallsStopIteration

tool_json = {
    "name": "tool_calls_end",
    "description": "停止当前回复,适用于:调用一些工具后已经完成任务,不需要继续回复用户的场景",
    "properties": None
}

async def main():
    raise ToolCallsStopIteration()


