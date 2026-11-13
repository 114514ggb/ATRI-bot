"""QQ 官方机器人事件 → OneBot 事件翻译

下游（ChatManager / GroupChat / 插件 / 命令）全部按 OneBot v11 的事件结构工作，
因此这里把官方 dispatch 事件重建为等价的 OneBot 字典，再交给 ``OneBotEvent.from_dict``。

同时把官方特有的元信息（openid、事件 id、附件列表）挂在
``primeval["_qqbot"]`` 上，供发送端做被动回复与后续查询。
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from atribot.core.platform.qqbot.id_map import QQBotIdMapper
from atribot.core.type.onebot_event_types import OneBotEvent

QQBOT_META_KEY = "_qqbot"
"""primeval 中存放官方事件元信息的键名"""


def safe_int(value: Any, default: int = 0) -> int:
    """尽力把字符串/数字转换为整数"""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_timestamp(value: Any) -> int:
    """解析官方事件时间戳（ISO8601 字符串或 Unix 秒）"""
    if value is None:
        return int(time.time())
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return int(time.time())
    if text.isdigit():
        return int(text)
    normalized = text.replace("Z", "+00:00")
    try:
        return int(datetime.datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return int(time.time())


def _attachment_segment(att: dict[str, Any]) -> dict[str, Any] | None:
    """把官方附件转换为 OneBot 消息段"""
    url = att.get("url")
    if not url:
        return None
    filename = str(att.get("filename") or att.get("name") or url)
    size = safe_int(att.get("size"), 0)
    content_type = str(att.get("content_type") or "").lower()

    if content_type.startswith("image"):
        return {
            "type": "image",
            "data": {"file": filename, "url": url, "file_size": size},
        }
    if content_type.startswith("video"):
        return {
            "type": "video",
            "data": {"file": filename, "url": url, "file_size": size},
        }
    if content_type.startswith("audio") or "voice" in content_type or "silk" in content_type:
        return {
            "type": "record",
            "data": {"file": filename, "url": url, "file_size": size},
        }
    return {
        "type": "file",
        "data": {"file": filename, "url": url, "file_size": size},
    }


def _build_segments(content: str, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    if content:
        segments.append({"type": "text", "data": {"text": content}})
    for att in attachments:
        if isinstance(att, dict):
            segment = _attachment_segment(att)
            if segment is not None:
                segments.append(segment)
    return segments


def _meta(
    event_type: str,
    data: dict[str, Any],
    *,
    group_openid: str | None,
    user_openid: str | None,
    event_id: str | None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "group_openid": group_openid,
        "user_openid": user_openid,
        "event_id": event_id,
        "raw_message_id": str(data.get("id") or ""),
        "attachments": data.get("attachments") or [],
    }


def _nickname_for(user_openid: str, author: dict[str, Any]) -> str:
    username = author.get("username")
    if username:
        return str(username)
    tail = user_openid[-6:] if user_openid else "unknown"
    return f"用户{tail}"


def build_event(
    payload: dict[str, Any],
    *,
    id_mapper: QQBotIdMapper,
    self_id: int,
) -> OneBotEvent | None:
    """把一条官方 dispatch payload 翻译成 OneBot 事件

    Args:
        payload: 网关下发的完整 payload（含 ``t`` / ``d``）
        id_mapper: openid → 整数 ID 映射
        self_id: 机器人自身 ID（整数形式）

    Returns:
        OneBot 事件实例；无法识别或无需处理的事件返回 None
    """
    event_type = str(payload.get("t") or "")
    data = payload.get("d")
    if not isinstance(data, dict):
        return None

    event_id = str(payload.get("id") or "")
    timestamp = data.get("timestamp") or data.get("time")
    event_time = parse_timestamp(timestamp)

    if event_type in ("GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
        return _build_message_event(
            event_type,
            data,
            id_mapper=id_mapper,
            self_id=self_id,
            event_time=event_time,
            event_id=event_id,
        )

    if event_type in ("GROUP_ADD_ROBOT", "GROUP_DEL_ROBOT"):
        group_openid = str(data.get("group_openid") or "")
        group_id = id_mapper.to_id("group", group_openid)
        operator_id = id_mapper.to_id("user", str(data.get("op_member_openid") or ""))
        meta = _meta(
            event_type,
            data,
            group_openid=group_openid or None,
            user_openid=str(data.get("op_member_openid") or "") or None,
            event_id=event_id,
        )
        raw: dict[str, Any] = {
            "post_type": "notice",
            "notice_type": "group_increase" if event_type == "GROUP_ADD_ROBOT" else "group_decrease",
            "sub_type": "approve" if event_type == "GROUP_ADD_ROBOT" else "kick_me",
            "time": event_time,
            "self_id": self_id,
            "group_id": group_id,
            "user_id": self_id,
            "operator_id": operator_id,
            QQBOT_META_KEY: meta,
        }
        return _from_dict(raw)

    if event_type in ("FRIEND_ADD", "FRIEND_DEL"):
        user_openid = str(data.get("openid") or "")
        user_id = id_mapper.to_id("user", user_openid)
        meta = _meta(
            event_type,
            data,
            group_openid=None,
            user_openid=user_openid or None,
            event_id=event_id,
        )
        raw = {
            "post_type": "notice",
            "notice_type": "friend_add" if event_type == "FRIEND_ADD" else "friend_del",
            "time": event_time,
            "self_id": self_id,
            "user_id": user_id,
            QQBOT_META_KEY: meta,
        }
        return _from_dict(raw)

    return None


def _build_message_event(
    event_type: str,
    data: dict[str, Any],
    *,
    id_mapper: QQBotIdMapper,
    self_id: int,
    event_time: int,
    event_id: str,
) -> OneBotEvent | None:
    author = data.get("author") if isinstance(data.get("author"), dict) else {}
    content = str(data.get("content") or "")
    attachments = [item for item in (data.get("attachments") or []) if isinstance(item, dict)]
    raw_message_id = str(data.get("id") or "")

    is_group = event_type == "GROUP_AT_MESSAGE_CREATE"
    group_openid = str(data.get("group_openid") or "") if is_group else ""
    if is_group:
        user_openid = str(author.get("member_openid") or "")
    else:
        user_openid = str(author.get("user_openid") or "")
    if not user_openid:
        # 兼容部分事件只下发 author.id / union_openid 的情况
        user_openid = str(author.get("id") or author.get("union_openid") or "")

    user_id = id_mapper.to_id("user", user_openid)
    message_id = id_mapper.to_id("message", raw_message_id)
    nickname = _nickname_for(user_openid, author)

    raw: dict[str, Any] = {
        "post_type": "message",
        "message_type": "group" if is_group else "private",
        "time": event_time,
        "self_id": self_id,
        "message_id": message_id,
        "user_id": user_id,
        "message": _build_segments(content, attachments),
        "raw_message": content,
        "sender": {
            "user_id": user_id,
            "nickname": nickname,
            "card": "",
            "role": "member",
        },
        QQBOT_META_KEY: _meta(
            event_type,
            data,
            group_openid=group_openid or None,
            user_openid=user_openid or None,
            event_id=event_id,
        ),
    }

    if is_group:
        raw["group_id"] = id_mapper.to_id("group", group_openid)
        raw["sub_type"] = "normal"
    else:
        raw["sub_type"] = "friend"

    event = _from_dict(raw)
    if event is None:
        return None

    # 群聊里能收到这条事件本身就意味着消息 @ 了机器人
    if is_group and hasattr(event, "is_at"):
        event.is_at = True
    return event


def _from_dict(raw: dict[str, Any]) -> OneBotEvent | None:
    try:
        return OneBotEvent.from_dict(raw)
    except Exception:  # noqa: BLE001 - 翻译失败不应打断网关
        return None
