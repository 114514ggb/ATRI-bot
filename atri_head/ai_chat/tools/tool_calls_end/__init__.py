tool_json = {
    "name": "tool_calls_end",
    "description": "主动终止当前文工具调用循环，不再回复user,适用于：1.不需要你回复 2.仅需执行语音播报后的终止 3.会话流程需保持静默",
    "properties": None
}

async def main():
    return {"tool_calls_end": "已经退出工具调用循环"}


