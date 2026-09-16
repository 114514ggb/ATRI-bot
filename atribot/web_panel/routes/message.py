"""适配器接口调用：通过平台适配器的 call_api 调用任意端点并返回原始 JSON"""

import asyncio
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from atribot.core.service_container import container

from ..deps import _auth

router = APIRouter()

_CALL_TIMEOUT = 30  # 秒；WS echo 自身 15 秒超时，这里兜底 HTTP 模式的连接挂起


class CallApiBody(BaseModel):
    platform: str
    action: str
    params: Dict[str, Any] = {}


@router.post("/api/message/call")
async def api_call(body: CallApiBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    from atribot.core.platform.manager import PlatformManager

    try:
        pm = container.get_by_type(PlatformManager)
    except Exception:
        return {"status": "error", "result": "平台管理器不可用"}

    adapters = pm.adapters
    if not adapters:
        return {"status": "error", "result": "没有可用适配器"}

    adapter = adapters.get(body.platform)
    if adapter is None:
        return {
            "status": "error",
            "result": f"适配器 '{body.platform}' 不存在，可用：{', '.join(adapters)}",
        }

    start = time.time()
    try:
        result = await asyncio.wait_for(
            adapter.call_api(body.action, body.params), timeout=_CALL_TIMEOUT
        )
    except asyncio.TimeoutError:
        return {
            "status": "error",
            "result": f"调用超时（{_CALL_TIMEOUT} 秒）",
            "duration_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "status": "error",
            "result": str(e) or repr(e),
            "duration_ms": int((time.time() - start) * 1000),
        }
    return {
        "status": "ok",
        "result": result,
        "duration_ms": int((time.time() - start) * 1000),
    }
