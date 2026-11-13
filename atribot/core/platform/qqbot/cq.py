"""CQ 码字符串解析

QQ 官方机器人没有 NapCat 那样的服务端 CQ 码解析，发送前需要自己把
``[CQ:reply,id=..]text[CQ:image,file=..]`` 拆成 OneBot 消息段字典。
"""

from __future__ import annotations

import re
from typing import Any

_CQ_PATTERN = re.compile(r"\[CQ:([A-Za-z0-9_\-./]+)((?:,[^\[\]]*)?)\]")

_UNESCAPE_PAIRS = (
    ("&#91;", "["),
    ("&#93;", "]"),
    ("&#44;", ","),
    ("&amp;", "&"),
)


def unescape_cq_text(text: str) -> str:
    """还原 CQ 参数中被转义的字符"""
    for escaped, raw in _UNESCAPE_PAIRS:
        text = text.replace(escaped, raw)
    return text


def _parse_params(param_str: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in param_str.split(","):
        if not item:
            continue
        key, sep, value = item.partition("=")
        key = key.strip()
        if not key:
            continue
        params[key] = unescape_cq_text(value) if sep else ""
    return params


def parse_cq_string(message: str) -> list[dict[str, Any]]:
    """把 CQ 码字符串解析为 OneBot 消息段列表

    Args:
        message: CQ 码字符串，例如 ``[CQ:reply,id=1]你好[CQ:image,file=file:///a.png]``

    Returns:
        ``[{"type": ..., "data": {...}}, ...]``；纯文本片段会合并为 text 段
    """
    if not message:
        return []

    segments: list[dict[str, Any]] = []
    position = 0

    for match in _CQ_PATTERN.finditer(message):
        if match.start() > position:
            text = unescape_cq_text(message[position:match.start()])
            if text:
                segments.append({"type": "text", "data": {"text": text}})

        seg_type = match.group(1)
        data = _parse_params(match.group(2).lstrip(","))

        if seg_type == "reply":
            data = {"id": data.get("id", "")}
        elif seg_type == "at":
            data = {"qq": data.get("qq", "")}

        segments.append({"type": seg_type, "data": data})
        position = match.end()

    if position < len(message):
        text = unescape_cq_text(message[position:])
        if text:
            segments.append({"type": "text", "data": {"text": text}})

    return segments
