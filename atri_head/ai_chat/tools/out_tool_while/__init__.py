tool_json = {
    "name": "out_tool_while",
    "description": "主动终止当前文本生成机会,适用于：1.不需要你回复 2.仅需执行语音播报 3.会话流程需保持静默",
    "properties": None
}

async def main():
    return {"out_tool_while": "已经退出工具调用循环"}