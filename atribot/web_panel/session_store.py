"""面板会话令牌存储（内存态）

登录页用主令牌（面板口令）换取会话令牌后，其余端点一律只认会话令牌：
- 令牌为 256 位随机值（``secrets.token_urlsafe(32)``）；表中只存 SHA-256 摘要，
  避免内存转储 / 调试输出时直接泄漏可用凭证；
- 固定有效期（默认 4 小时，由 deps 从 ``web_panel.session_ttl_hours`` 解析），到期即失效；
- 容量上限 ``MAX_SESSIONS``，满载时逐出最早到期者；
- 进程重启即清空；主令牌轮换时由 deps 调用 :func:`revoke_all` 清空全部会话；
- WebSocket 握手另有一次性短票据（:func:`create_ws_ticket` / :func:`consume_ws_ticket`），
  避免把长期有效的会话令牌放进 WS URL（浏览器/代理日志会记录 query）；
- 线程安全：鉴权函数可能在请求线程中执行，统一用锁保护。
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from typing import Dict, Optional

MAX_SESSIONS = 100
"""会话容量上限（单人自托管面板远达不到，纯粹防御性上限）"""

TICKET_TTL_SECONDS = 30.0
"""WS 一次性票据默认有效期（秒）：前端取票后立即建连，30 秒足够"""

MAX_TICKETS = 200
"""未使用票据的容量上限（防御性上限，满载时逐出最早到期者）"""

DEFAULT_TTL_SECONDS = 4 * 3600
"""默认会话有效期：4 小时"""

MIN_TTL_HOURS = 1
MAX_TTL_HOURS = 24
"""会话有效期的可配置范围（小时），``web_panel.session_ttl_hours`` 会按此钳制"""

_lock = threading.Lock()
_sessions: Dict[str, float] = {}
"""令牌摘要（SHA-256 十六进制）→ 到期时间（time.monotonic() 秒）"""

_tickets: Dict[str, tuple] = {}
"""票据摘要 → (会话摘要, 到期时间)；单次使用，消费即删除"""


def token_digest(token: str) -> str:
    """令牌/票据摘要：表内只存摘要，WS 复验与登出都按摘要定位"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _purge_expired_locked(now: float) -> None:
    for digest in [d for d, expires in _sessions.items() if expires <= now]:
        _sessions.pop(digest, None)


def _purge_expired_tickets_locked(now: float) -> None:
    for digest in [d for d, (_, expires) in _tickets.items() if expires <= now]:
        _tickets.pop(digest, None)


def create_session(ttl_seconds: float) -> str:
    """签发一枚新会话令牌并登记到期时间；返回明文令牌（仅此一次可见）"""
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        _purge_expired_locked(now)
        while len(_sessions) >= MAX_SESSIONS:
            # 满载：逐出最早到期者（等价于最早签发者）
            oldest = min(_sessions, key=_sessions.__getitem__)
            _sessions.pop(oldest, None)
        _sessions[token_digest(token)] = now + max(1.0, float(ttl_seconds))
    return token


def validate_session(token: str) -> bool:
    """会话令牌是否有效（空令牌 / 未登记 / 过期均为 False）"""
    return bool(token) and validate_digest(token_digest(token))


def revoke_session(token: str) -> bool:
    """吊销单枚会话令牌（登出用）；返回是否命中"""
    if not token:
        return False
    with _lock:
        return _sessions.pop(token_digest(token), None) is not None


def validate_digest(digest: str) -> bool:
    """按摘要校验会话（validate_session 与 WS 建连/复验都走这里）"""
    if not digest:
        return False
    now = time.monotonic()
    with _lock:
        expires = _sessions.get(digest)
        if expires is None:
            return False
        if expires <= now:
            _sessions.pop(digest, None)
            return False
        return True


def create_ws_ticket(session_token: str, ttl_seconds: float = TICKET_TTL_SECONDS) -> Optional[str]:
    """为有效会话签发一次性 WS 票据；会话无效时返回 None

    票据明文只在返回值中出现一次，表内只存摘要；单次使用 + 短有效期，
    避免把长期有效的会话令牌放进 WebSocket URL。
    """
    if not session_token:
        return None
    digest = token_digest(session_token)
    now = time.monotonic()
    with _lock:
        if _sessions.get(digest, 0.0) <= now:
            return None
        _purge_expired_tickets_locked(now)
        while len(_tickets) >= MAX_TICKETS:
            oldest = min(_tickets, key=lambda d: _tickets[d][1])
            _tickets.pop(oldest, None)
        ticket = secrets.token_urlsafe(32)
        _tickets[token_digest(ticket)] = (digest, now + max(1.0, float(ttl_seconds)))
    return ticket


def consume_ws_ticket(ticket: str) -> Optional[str]:
    """消费票据：成功返回绑定的会话摘要（供后续复验），过期/重复使用返回 None"""
    if not ticket:
        return None
    now = time.monotonic()
    with _lock:
        entry = _tickets.pop(token_digest(ticket), None)
        if entry is None:
            return None
        session_digest, expires = entry
        if expires <= now or _sessions.get(session_digest, 0.0) <= now:
            return None
        return session_digest


def revoke_all() -> int:
    """清空全部会话与票据（主令牌轮换时调用）；返回被清除的会话数"""
    with _lock:
        count = len(_sessions)
        _sessions.clear()
        _tickets.clear()
        return count


def session_count() -> int:
    """当前有效会话数量（先清过期再计数）"""
    now = time.monotonic()
    with _lock:
        _purge_expired_locked(now)
        return len(_sessions)
