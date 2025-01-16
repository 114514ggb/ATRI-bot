from datetime import datetime

def main():
    """获取当前时间"""

    current_datetime = datetime.now()

    formatted_time = current_datetime.strftime('%Y-%m-%d %H:%M:%S')
    print(formatted_time)

    return {"北京_time":formatted_time}