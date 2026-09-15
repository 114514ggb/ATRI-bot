"""消息发送：通过平台适配器发送私聊 / 群消息"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atribot.core.service_container import container

from ..deps import _auth

router = APIRouter()


class SendMsgBody(BaseModel):
    group_id: Optional[int] = None
    user_id: Optional[int] = None
    message: str | list
    platform: Optional[str] = None


@router.post("/api/message/send")
async def api_send_message(body: SendMsgBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    from atribot.core.platform.manager import PlatformManager

    if body.group_id is None and body.user_id is None:
        raise HTTPException(status_code=400, detail="必须提供 group_id（群聊）或 user_id（私聊）")

    try:
        pm = container.get_by_type(PlatformManager)
    except Exception:
        return {"status": "error", "result": "平台管理器不可用"}

    adapters = pm.adapters
    if not adapters:
        return {"status": "error", "result": "没有可用适配器"}

    if body.platform and body.platform in adapters:
        adapter = adapters[body.platform]
    else:
        adapter = next(iter(adapters.values()))

    client = adapter.get_client()
    if body.user_id is not None:
        action, payload = "send_private_msg", {"user_id": body.user_id, "message": body.message}
    else:
        action, payload = "send_group_msg", {"group_id": body.group_id, "message": body.message}
    result = await client.async_send(action, payload)
    return {"status": "ok", "result": result}
