import datetime


def construction_message_dict(template: list[dict], url_prefix: str = "") -> list[dict]:
    """
    将包含image和text的字典转换为指定格式的消息列表（按原始键顺序）
    
    Args:
        template (dict): 包含"image"和/或"text"键的字典
        url_prefix (str): 图片文件路径的前缀,会统一加在所有前面\n
            本地路径:"file://D:/a.jpg"\n
            网络路径:"http://123456.com/a.jpg"\n
            base64编码:"base64://xxx"
            
    Returns:
        list[dict]: 转换后的消息字典列表
    
    Example:
        input: [{"image":"ATRI_思考.jpg"},{"text":"是思考啊"}]
        output: [
            {"type": "image", "data": {"file": "path/ATRI_思考.jpg"}},
            {"type": "text", "data": {"text": "是思考啊"}}
        ]
    """
    result = []
    
    for item in template:
        for key, value in item.items():
            if not value:
                continue
            
            if key == "image":
                image_path = url_prefix + value if url_prefix else value
                result.append({
                    "type": "image",
                    "data": {
                        "file": image_path
                    }
                })
            elif key == "text":
                result.append({
                    "type": "text",
                    "data": {
                        "text": value
                    }
                })
    
    return result


def format_duration(seconds: int) -> str:
    """将秒数转换为易读的时间格式
    
    Args:
        seconds (int): 秒数
        
    Returns:
        str: 格式化后的时间字符串，如 "1天2小时3分钟4秒"
    """
    if seconds == 0:
        return "0秒"

    units = [
        (86400, "天"),
        (3600, "小时"),
        (60, "分钟"),
        (1, "秒"),
    ]

    parts: list[str] = []
    remaining = seconds

    for unit_seconds, unit_name in units:
        if remaining >= unit_seconds:
            count = remaining // unit_seconds
            remaining %= unit_seconds
            parts.append(f"{count}{unit_name}")

    return "".join(parts)


def parse_time_to_timestamp(time_str: str, is_end_time: bool = False) -> int | None:
    """
    将日期时间字符串转换为时间戳。

    支持 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS' 格式的输入。
    对于结束时间且输入仅为日期格式时，会自动设置为当天的 23:59:59。

    Args:
        time_str: 日期时间字符串，例如 '2024-01-01' 或 '2024-01-01 12:30:45'
        is_end_time: 是否为结束时间标志。当为 True 且输入仅为日期时，
                    时间会被设置为当天的最后一秒。

    Returns:
        对应的 Unix 时间戳（整数）。如果输入为空或格式不匹配则返回 None。
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