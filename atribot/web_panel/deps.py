"""面板共享基础设施：鉴权与 DI 辅助、日志环形缓冲、配置文件读写工具

各功能域路由按页面拆分在 routes/ 包内，此处只放被多个模块共用的东西。
所有服务依赖均为惰性获取（请求内从 DI 容器解析），
使面板可以在不完整的运行环境中安全导入与独立调试。
"""

import hashlib
import json
import logging
import os
import secrets
import shutil
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atribot.core.service_container import container

from . import session_store

log = logging.getLogger("atri-bot.WebPanel")

_LOG_BUFFER_MAX = 500
_log_buffer: deque = deque(maxlen=_LOG_BUFFER_MAX)
_log_seq = 0
_log_buffer_lock = Lock()


# 第三方库的 DEBUG/INFO 帧/心跳日志（websockets 的 > TEXT / PING / PONG 等）过于嘈杂，
# 面板日志流对这类来源只收录 WARNING 及以上；自家日志（atri-bot.* 等）不受影响
_NOISY_LOGGERS = ("websockets.", "asyncio", "httpx.", "httpcore.", "urllib3", "aiohttp.")


class _PanelLogHandler(logging.Handler):
    """将日志记录追加进环形缓冲，供 WebSocket 日志流消费"""

    def emit(self, record: logging.LogRecord) -> None:
        global _log_seq
        try:
            if record.levelno < logging.WARNING and record.name.startswith(_NOISY_LOGGERS):
                return
            now = datetime.now()
            _log_seq += 1
            _log_buffer.append(
                {
                    "seq": _log_seq,
                    "time": f"{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}",
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:
            pass


def _ensure_log_handler() -> None:
    root = logging.getLogger()
    if any(isinstance(h, _PanelLogHandler) for h in root.handlers):
        return
    # DEBUG 级别：面板日志流需要展示 atri-bot.* 的 DEBUG 输出
    root.addHandler(_PanelLogHandler(level=logging.DEBUG))
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)


def _cfg():
    return container.get("config")


def _db():
    return container.get("database")


_MIN_TOKEN_LEN = 8
"""主令牌最小建议长度：短于此值在首次读取时告警（不阻断运行）"""

_master_token_seen: Optional[str] = None
"""上次读取到的主令牌摘要（SHA-256），用于检测轮换并清空旧会话"""

_weak_token_warned = False


def weak_token_reasons(token: str) -> list:
    """主令牌过弱的原因列表（空列表 = 通过）；登录端点与启动告警共用"""
    reasons = []
    if len(token) < _MIN_TOKEN_LEN:
        reasons.append(f"长度不足 {_MIN_TOKEN_LEN} 字符")
    try:
        for name, platform in (_cfg()._raw_config.get("platforms") or {}).items():
            if isinstance(platform, dict) and platform.get("access_token") == token:
                reasons.append(f"与平台 {name} 的 access_token 相同")
                break
    except Exception:
        pass
    return reasons


WEAK_TOKEN_HINT = (
    "请在 config.json 的 web_panel.access_token 或环境变量 ATRI_PANEL_TOKEN "
    '设置 32 字符以上随机值：python -c "import secrets; print(secrets.token_urlsafe(32))"'
)


def weak_token_blocked() -> bool:
    """是否硬性拒绝弱主令牌登录：web_panel.block_weak_token（默认 false，仅告警不阻断）"""
    try:
        return bool((_cfg()._raw_config.get("web_panel") or {}).get("block_weak_token"))
    except Exception:
        return False


def _warn_weak_token(token: str) -> None:
    """弱主令牌告警（进程生命周期内只提示一次）"""
    global _weak_token_warned
    if _weak_token_warned:
        return
    reasons = weak_token_reasons(token)
    if reasons:
        _weak_token_warned = True
        log.warning("面板主令牌过弱（%s），%s", "；".join(reasons), WEAK_TOKEN_HINT)


def _access_token() -> Optional[str]:
    """面板主令牌（登录口令）:web_panel.access_token > 环境变量 ATRI_PANEL_TOKEN

    不回退到平台 access_token（避免 OneBot 凭据等同于面板口令）；未配置时返回 None，
    各鉴权入口据此返回 503（fail-closed）。每次读取顺带做两件事：
    - 弱口令检测（warn-once）；
    - 主令牌轮换检测：摘要变化即清空全部会话，强制重新登录。
    """
    global _master_token_seen
    try:
        raw = _cfg()._raw_config
        token = (raw.get("web_panel") or {}).get("access_token") or os.environ.get("ATRI_PANEL_TOKEN")
    except Exception:
        token = os.environ.get("ATRI_PANEL_TOKEN")
    token = token or None

    digest = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else None
    if _master_token_seen is not None and digest != _master_token_seen:
        # 主令牌轮换 / 被清空：旧会话全部作废，强制重新登录
        cleared = session_store.revoke_all()
        if cleared:
            log.warning("检测到面板主令牌变更，%d 个旧会话全部作废", cleared)
    _master_token_seen = digest

    if token:
        _warn_weak_token(token)
    return token


_security = HTTPBearer(auto_error=False)

_NO_TOKEN_DETAIL = "未配置访问令牌：请在 config.json 添加 web_panel.access_token 或设置环境变量 ATRI_PANEL_TOKEN"


# ---------- 登录防暴力破解：全局统一计数（不区分来源 IP） ----------
# 任何来源的错误尝试都累计到同一计数器：连续失败达到 _LOGIN_FAIL_THRESHOLD 次即触发锁定，
# 时长 _LOCK_BASE_SECONDS × 2^(失败次数-阈值)，封顶 _LOCK_MAX_SECONDS（24 小时）。
# 锁定期内所有登录请求一律 429（即使口令正确也不放行，用户明确要求的硬锁定）；
# 锁定期内的新失败不计数、不续期；登录成功清零。计数与锁定为进程内存态，重启即清空。
#
# 注意：这是「防爆破优先于可用性」的取舍——外部可故意多次输错把面板锁在门外。
# 缓解：锁定只拦登录端点，已登录会话不受影响；重启进程可立即清空锁定。

_LOGIN_FAIL_THRESHOLD = 3
_LOCK_BASE_SECONDS = 600
_LOCK_MAX_SECONDS = 86400

_login_failures = 0
_lock_until = 0.0  # 锁定截止时间（time.monotonic() 秒）
_login_lock = Lock()


def _lockout_seconds(fails: int) -> int:
    """第 fails 次连续失败对应的锁定时长（仅 fails >= 阈值时有意义）"""
    return min(_LOCK_BASE_SECONDS * (2 ** (fails - _LOGIN_FAIL_THRESHOLD)), _LOCK_MAX_SECONDS)


def login_lock_remaining() -> Optional[float]:
    """登录是否处于锁定期：是则返回剩余秒数，否则 None"""
    with _login_lock:
        remaining = _lock_until - time.monotonic()
        return remaining if remaining > 0 else None


def login_failures() -> int:
    """当前连续失败次数（用于登录错误提示）"""
    with _login_lock:
        return _login_failures


def register_login_failure() -> Optional[float]:
    """登记一次登录失败；达到阈值则进入锁定并返回剩余秒数，否则返回 None"""
    global _login_failures, _lock_until
    with _login_lock:
        _login_failures += 1
        if _login_failures < _LOGIN_FAIL_THRESHOLD:
            return None
        _lock_until = time.monotonic() + _lockout_seconds(_login_failures)
        return max(0.0, _lock_until - time.monotonic())


def clear_login_failures() -> None:
    """登录成功：清零失败计数并解除锁定"""
    global _login_failures, _lock_until
    with _login_lock:
        _login_failures = 0
        _lock_until = 0.0


def verify_master_token(candidate: str) -> bool:
    """常量时间比较主令牌（仅登录端点调用）"""
    expected = _access_token()
    if not expected:
        return False
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def _session_ttl_seconds() -> int:
    """会话有效期（秒）：web_panel.session_ttl_hours（默认 4，钳制 1-24 小时）"""
    hours: float = session_store.DEFAULT_TTL_SECONDS / 3600
    try:
        raw = (_cfg()._raw_config.get("web_panel") or {}).get("session_ttl_hours")
        if raw is not None:
            hours = float(raw)
    except Exception:
        pass
    hours = max(session_store.MIN_TTL_HOURS, min(session_store.MAX_TTL_HOURS, hours))
    return int(hours * 3600)


def _require_session(token: str) -> None:
    """会话令牌校验（HTTP 端点共用）：未配置主令牌 503，令牌无效/过期 401"""
    if not _access_token():
        raise HTTPException(status_code=503, detail=_NO_TOKEN_DETAIL)
    if not session_store.validate_session(token):
        raise HTTPException(status_code=401, detail="会话不存在或已过期，请重新登录")


def _session_digest_valid(digest: str) -> bool:
    """会话摘要当前是否可用（主令牌已配置且未过期/被吊销）；WS 建连与复验共用"""
    return bool(_access_token()) and session_store.validate_digest(digest)


async def _auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> str:
    """HTTP 端点鉴权：只认会话令牌（Authorization: Bearer <会话令牌>），返回该令牌

    主令牌仅用于 POST /api/login 换取会话令牌，不再直接放行任何端点。
    """
    token = creds.credentials if creds is not None else ""
    _require_session(token)
    return token


async def _ws_auth(websocket, token: str = "", ticket: str = "") -> Optional[str]:
    """WebSocket 握手鉴权：优先一次性票据（?ticket=），兼容旧 ?token=（会话令牌）

    成功返回「会话摘要」，后续用 :func:`_ensure_ws_session` 复验；失败以 4401 关闭并返回 None。
    注意必须先 accept 再 close：accept 之前 close 会被 uvicorn 转成 HTTP 403
    拒绝握手，浏览器端只能看到抽象的 1006，自定义 close code 永远到不了前端，
    导致前端无法展示真实失败原因。
    """
    await websocket.accept()
    if ticket:
        session_ref: Optional[str] = session_store.consume_ws_ticket(ticket)
    elif token:
        # 兼容旧 ?token= 通道：统一转成摘要，与票据走同一套复验
        session_ref = session_store.token_digest(token)
    else:
        session_ref = None
    if session_ref and _session_digest_valid(session_ref):
        return session_ref
    await websocket.close(code=4401)
    return None


async def _ensure_ws_session(websocket, session_ref: str) -> bool:
    """WS 建连后的会话复验：失效则以 4401 关闭并返回 False

    否则「登录一次、长连接终身有效」，登出 / 过期 / 主令牌轮换都拦不住已建立的连接。
    参数为 :func:`_ws_auth` 返回的会话摘要（票据与令牌两条通道统一）。
    """
    if _session_digest_valid(session_ref):
        return True
    await websocket.close(code=4401)
    return False


def _chat_manager():
    """获取 ChatManager（可能未启动，如独立调试时）"""
    from atribot.core.cache.management_chat_example import ChatManager

    try:
        return container.get_by_type(ChatManager)
    except Exception:
        return None


def _backup_file(path) -> Path:
    path = Path(path)
    backup = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, backup)
    return backup


def _write_json(path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def _read_config_text(path) -> tuple:
    """读取配置文件：合法则返回规范化文本，否则原样返回并标记 invalid"""
    raw = path.read_text(encoding="utf-8")
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2), True
    except (json.JSONDecodeError, ValueError):
        return raw, False


def _parse_json_or_400(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: 第 {e.lineno} 行第 {e.colno} 列 - {e.msg}")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="配置根节点必须是 JSON 对象 {{...}}")
    return parsed


async def _safe_count(sql: str, args: tuple = ()) -> int:
    try:
        rows = await _db().execute_SQL(sql, args)
        return rows[0]["c"] if rows else 0
    except Exception:
        return 0
