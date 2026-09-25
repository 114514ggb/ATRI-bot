"""存储层文本清洗工具

平台侧传入的文本混入二进制垃圾时可能包含 PostgreSQL 无法存储的字符
（尤其是 NUL(U+0000)，text/jsonb 类型硬性禁止），本模块提供"出错后清洗"所需的
纯函数，仅在数据库写入因编码错误失败时按需调用，正常路径不做任何处理。
"""

from typing import Any

_C0_CONTROL_CHARS = "".join(
    chr(code) for code in range(0x20) if code not in (0x09, 0x0A, 0x0D)
)
"""C0 控制字符集合（保留制表符、换行与回车）"""

_CONTROL_TRANSLATION_TABLE = str.maketrans({char: None for char in _C0_CONTROL_CHARS})
"""str.translate 查表：命中即删除"""


def sanitize_text(value: str) -> str:
    """删除字符串中的 NUL 与 C0 控制字符（保留制表符、换行、回车）

    PostgreSQL 的 text / jsonb 类型不允许存储 NUL(U+0000)，
    其余 C0 控制字符虽可存储但属于无意义内容，一并清洗。

    Args:
        value: 原始字符串

    Returns:
        清洗后的字符串；无匹配字符时原样返回
    """
    return value.translate(_CONTROL_TRANSLATION_TABLE)


def sanitize_db_params(params: Any) -> tuple[Any, int]:
    """递归清洗数据库参数中字符串的非法字符

    支持 str / tuple / list / dict（dict 的键与值均处理），
    bytes、bytearray 及其它类型原样保留。

    Args:
        params: 数据库参数（通常为元组，也支持嵌套容器）

    Returns:
        (清洗后的参数, 移除的字符数)；移除字符数为 0 表示参数未被修改
    """
    if isinstance(params, str):
        cleaned = sanitize_text(params)
        return cleaned, len(params) - len(cleaned)

    if isinstance(params, (tuple, list)):
        removed = 0
        cleaned_items: list[Any] = []
        for item in params:
            cleaned_item, item_removed = sanitize_db_params(item)
            cleaned_items.append(cleaned_item)
            removed += item_removed
        if removed == 0:
            return params, 0
        return type(params)(cleaned_items), removed

    if isinstance(params, dict):
        removed = 0
        cleaned_dict: dict[Any, Any] = {}
        for key, value in params.items():
            cleaned_key, key_removed = sanitize_db_params(key)
            cleaned_value, value_removed = sanitize_db_params(value)
            cleaned_dict[cleaned_key] = cleaned_value
            removed += key_removed + value_removed
        if removed == 0:
            return params, 0
        return cleaned_dict, removed

    return params, 0
