from datetime import datetime

tool_json = {
    "name": "get_current_time",
    "description": "当你想知道现在的北京时间时非常有用",
    "properties": None
}

async def main():
    """获取当前时间"""

    current_datetime = datetime.now()

    formatted_time = current_datetime.strftime('%Y-%m-%d %H:%M:%S')
    # print(formatted_time)

    return {"北京_time":formatted_time}