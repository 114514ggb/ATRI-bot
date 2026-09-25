"""登录/登出：用主令牌换取会话令牌（面板唯一的口令校验入口）

其余端点全部只认会话令牌（见 deps 的 ``_require_session`` / ``_ws_auth`` / ``_ensure_ws_session``）。
登录失败采用全局统一计数（不区分来源 IP）：连续失败达阈值触发硬锁定，
锁定期内即使口令正确也一律 429，直到锁定结束（策略与取舍详见 deps 顶部注释）。
"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import session_store
from ..deps import (
    _LOGIN_FAIL_THRESHOLD,
    _NO_TOKEN_DETAIL,
    WEAK_TOKEN_HINT,
    _access_token,
    _auth,
    _session_ttl_seconds,
    clear_login_failures,
    login_failures,
    login_lock_remaining,
    register_login_failure,
    verify_master_token,
    weak_token_blocked,
    weak_token_reasons,
)

router = APIRouter()

log = logging.getLogger("atri-bot.WebPanel")


class LoginBody(BaseModel):
    token: str = ""


def _lockout_error(remaining: float) -> HTTPException:
    """锁定期统一错误：429 + Retry-After（remaining 为剩余锁定秒数）"""
    seconds = int(remaining) + 1
    return HTTPException(
        status_code=429,
        detail=f"尝试次数过多，请 {seconds} 秒后重试",
        headers={"Retry-After": str(seconds)},
    )


@router.post("/api/login")
async def api_login(payload: LoginBody, request: Request) -> Dict[str, object]:
    """主令牌换取会话令牌；失败：401（附剩余尝试次数）/ 403（block_weak_token 且口令过弱）/ 429（锁定期，带 Retry-After）/ 503（未配置主令牌）"""
    master = _access_token()
    if not master:
        raise HTTPException(status_code=503, detail=_NO_TOKEN_DETAIL)

    if weak_token_blocked():
        reasons = weak_token_reasons(master)
        if reasons:
            raise HTTPException(
                status_code=403,
                detail=f"主令牌过弱（{'；'.join(reasons)}），已拒绝登录。{WEAK_TOKEN_HINT}",
            )

    remaining = login_lock_remaining()
    if remaining is not None:
        # 锁定期内一律拒绝（正确口令也不例外），且不计数、不续期
        raise _lockout_error(remaining)

    ip = request.client.host if request.client else "?"
    if not verify_master_token(payload.token):
        locked = register_login_failure()
        if locked is not None:
            log.warning("面板登录连续失败 %d 次（%s），已全局锁定 %d 秒", login_failures(), ip, int(locked) + 1)
            raise _lockout_error(locked)
        left = max(0, _LOGIN_FAIL_THRESHOLD - login_failures())
        log.warning("面板登录失败（%s）：口令错误，剩余尝试次数 %d", ip, left)
        raise HTTPException(status_code=401, detail=f"访问令牌错误（还可尝试 {left} 次）")

    clear_login_failures()
    ttl = _session_ttl_seconds()
    session_token = session_store.create_session(ttl)
    log.info("面板登录成功（%s），会话有效期 %d 分钟", ip, ttl // 60)
    return {"status": "ok", "session_token": session_token, "expires_in": ttl}


@router.post("/api/logout")
async def api_logout(token: str = Depends(_auth)) -> Dict[str, str]:
    """吊销当前会话令牌（会话无效时由 _auth 直接返回 401/503）"""
    session_store.revoke_session(token)
    return {"status": "ok"}


@router.post("/api/ws_ticket")
async def api_ws_ticket(token: str = Depends(_auth)) -> Dict[str, object]:
    """为当前会话签发一次性 WS 票据（WebSocket URL 不再携带长期会话令牌）

    票据 30 秒内有效、单次使用；前端每次（重）连前现取，
    即使被代收日志记录也无法用于后续连接。
    """
    ticket = session_store.create_ws_ticket(token)
    if not ticket:
        raise HTTPException(status_code=401, detail="会话不存在或已过期，请重新登录")
    return {"status": "ok", "ticket": ticket, "expires_in": int(session_store.TICKET_TTL_SECONDS)}
