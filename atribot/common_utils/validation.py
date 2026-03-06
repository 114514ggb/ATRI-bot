"""基础校验工具。"""


def is_qq(qq_id: str | int) -> bool:
    """判断是否是 qq 号。

    Args:
        qq_id: 要判断的 qq 标识。

    Returns:
        是否为合法 qq 号（仅数字，长度 5~11）。
    """
    qq_text = str(qq_id)
    if not qq_text.isdigit():
        return False
    return 5 <= len(qq_text) <= 11
