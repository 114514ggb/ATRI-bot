from datetime import datetime

tool_json = {
    "name": "get_current_time",
    "description": "获取当前的北京时间和日期",
    "properties": None
}

async def main():
    """获取当前时间"""

    return {"北京_time":datetime.now().strftime('%Y-%m-%d %H:%M:%S')}