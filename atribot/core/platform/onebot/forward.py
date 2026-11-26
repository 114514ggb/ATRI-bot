"""合并转发消息内容补全

OneBot 各实现上报 ``forward`` 消息段的方式不一致：

* NapCat：``{"type": "forward", "data": {"id": ..., "content": [节点...]}}``
  —— 节点自带完整内容，可直接解析；
* LLBot：``{"type": "forward", "data": {"id": "resId"}}``
  —— 只有 resId，必须再调用 ``get_forward_msg`` 才能读到里面的消息。

``ForwardSegment`` 依赖 ``content`` 才能把转发内容展开给 LLM，因此这里统一在
事件入队前做一次补全：已有 content 时只做本地规范化（不发请求），
缺失时调用 ``get_forward_msg`` 拉取，失败仅降级为只显示 id。
"""

import asyncio
import logging
from typing import Any

from atribot.core.platform.onebot.cqcode import cq_to_segments

FORWARD_FETCH_TIMEOUT = 8.0
"""拉取合并转发内容的超时时间(秒)，超时后降级为只显示 id"""


def normalize_forward_node(
    node: dict[str, Any],
    *,
    self_id: int = 0,
    group_id: int | None = None,
    fallback_time: int = 0,
) -> dict[str, Any]:
    """把转发节点补全成 ``OneBotEvent.from_dict`` 可解析的消息事件格式

    ``ForwardSegment.__str__`` 通过 ``OneBotEvent.from_dict`` 解析节点，
    要求节点带有 ``post_type`` / ``message`` / ``time`` / ``self_id``。

    Args:
        node: 转发节点，可能是 ``{content, sender, time, message_type}``（LLBot）
            或已是完整消息事件（NapCat）
        self_id: 外层事件的机器人 QQ 号，节点缺失时回填
        group_id: 外层事件的群号，节点缺失时回填
        fallback_time: 外层事件时间戳，节点缺失时回填

    Returns:
        规范化后的节点；无法识别时原样返回
    """
    if not isinstance(node, dict):
        return node

    message = node.get("content")
    if message is None:
        message = node.get("message")
    if isinstance(message, str):
        message = cq_to_segments(message)
    elif message is None:
        message = []

    if node.get("post_type"):
        # 已是完整事件：仅在缺少 message 时补上
        if node.get("message") is None:
            return {**node, "message": message}
        return node

    sender = node.get("sender") or {}
    return {
        "post_type": "message",
        "message_type": node.get("message_type") or ("group" if group_id else "private"),
        "sub_type": node.get("sub_type") or "normal",
        "time": node.get("time") or fallback_time,
        "self_id": node.get("self_id") or self_id,
        "message_id": node.get("message_id") or node.get("message_seq") or 0,
        "message_seq": node.get("message_seq") or node.get("message_id") or 0,
        "user_id": node.get("user_id") or sender.get("user_id") or 0,
        "group_id": node.get("group_id") or group_id or 0,
        "message": message,
        "raw_message": node.get("raw_message") or "",
        "sender": sender,
    }


def _extract_messages(resp: Any) -> list[dict[str, Any]]:
    """兼容 ``data.messages``（LLBot）与 ``data`` 为数组（NapCat/go-cqhttp）"""
    if not isinstance(resp, dict):
        return []
    data = resp.get("data")
    if isinstance(data, dict):
        messages = data.get("messages")
    else:
        messages = data
    return [m for m in messages if isinstance(m, dict)] if isinstance(messages, list) else []


async def fill_forward_content(
    send_client: Any,
    event: dict[str, Any],
    log: logging.Logger | None = None,
) -> dict[str, Any]:
    """为合并转发消息段补全/规范化 ``content``

    Args:
        send_client: 具备 ``async_send(action, params)`` 的发送客户端
        event: 原始消息事件字典
        log: 可选日志器

    Returns:
        处理后的事件字典（失败时保留原样，不影响消息入队）
    """
    message = event.get("message")
    if not isinstance(message, list) or not message:
        return event

    self_id = int(event.get("self_id") or 0)
    group_id = event.get("group_id")
    fallback_time = int(event.get("time") or 0)

    new_message = list(message)
    changed = False

    for i, seg in enumerate(message):
        if not isinstance(seg, dict) or seg.get("type") != "forward":
            continue
        data = seg.get("data") or {}
        content = data.get("content")

        if content:
            nodes = content if isinstance(content, list) else [content]
            new_message[i] = {
                "type": "forward",
                "data": {
                    **data,
                    "content": [
                        normalize_forward_node(
                            node,
                            self_id=self_id,
                            group_id=group_id,
                            fallback_time=fallback_time,
                        )
                        for node in nodes
                        if isinstance(node, dict)
                    ],
                },
            }
            changed = True
            continue

        forward_id = data.get("id")
        if not forward_id:
            continue

        forward_id = str(forward_id)
        try:
            resp = await asyncio.wait_for(
                send_client.async_send("get_forward_msg", {"id": forward_id}),
                timeout=FORWARD_FETCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            if log:
                log.warning("拉取合并转发超时(%ss): id=%s", FORWARD_FETCH_TIMEOUT, forward_id)
            continue
        except Exception as error:
            if log:
                log.warning("拉取合并转发失败: id=%s, error=%s", forward_id, error)
            continue

        nodes = _extract_messages(resp)
        if not nodes:
            if log:
                log.warning("合并转发内容为空: id=%s, resp=%s", forward_id, str(resp)[:200])
            continue

        new_message[i] = {
            "type": "forward",
            "data": {
                **data,
                "content": [
                    normalize_forward_node(
                        node,
                        self_id=self_id,
                        group_id=group_id,
                        fallback_time=fallback_time,
                    )
                    for node in nodes
                ],
            },
        }
        changed = True

    if not changed or new_message == message:
        return event
    return {**event, "message": new_message}
