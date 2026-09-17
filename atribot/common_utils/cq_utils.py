_CQ_ESCAPES = str.maketrans({"&": "&amp;", "[": "&#91;", "]": "&#93;", ",": "&#44;"})


def escape_cq_param(value: str) -> str:
    """按 OneBot v11 规则转义 CQ 码参数值中的特殊字符

    Args:
        value (str): 原始参数值

    Returns:
        str: 转义后的参数值
    """
    return value.translate(_CQ_ESCAPES)
