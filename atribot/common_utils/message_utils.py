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
