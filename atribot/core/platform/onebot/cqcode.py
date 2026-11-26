"""OneBot 11 CQ 码解析工具"""

import re
from typing import Any

_CQ_PATTERN = re.compile(r"\[CQ:([A-Za-z0-9_.-]+)((?:,[^\]]*)?)\]")
_CQ_ESCAPE = (
    ("&#91;", "["),
    ("&#93;", "]"),
    ("&#44;", ","),
    ("&amp;", "&"),
)


def _unescape(text: str) -> str:
    for escaped, raw in _CQ_ESCAPE:
        text = text.replace(escaped, raw)
    return text


def cq_to_segments(text: str) -> list[dict[str, Any]]:
    """把 CQ 码字符串转换为 OneBot 消息段数组

    部分实现（如 LLBot 的 ``message_format=string``）上报的 ``message`` 字段是
    CQ 码文本，而本项目的解析链路只接受数组，因此在这里做一次转换。
    """
    segments: list[dict[str, Any]] = []
    last = 0
    for match in _CQ_PATTERN.finditer(text):
        if match.start() > last:
            segments.append({"type": "text", "data": {"text": _unescape(text[last:match.start()])}})

        data: dict[str, str] = {}
        for item in (match.group(2) or "").split(",")[1:]:
            if "=" in item:
                key, value = item.split("=", 1)
                data[key] = _unescape(value)
        segments.append({"type": match.group(1), "data": data})
        last = match.end()

    if last < len(text):
        segments.append({"type": "text", "data": {"text": _unescape(text[last:])}})

    if not segments:
        segments.append({"type": "text", "data": {"text": text}})
    return segments
