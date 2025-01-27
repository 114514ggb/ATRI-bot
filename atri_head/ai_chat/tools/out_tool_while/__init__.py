tool_json = {
    "name": "out_tool_while",
    "description": "如果有必要的话调用此工具可以结束你的当次响应机会，适用于什么都不需要回复还有不需要你回答或者只需要发语音等情况",
    "properties": None
}

async def main():
    return {"out_tool_while": "已经退出工具调用循环"}