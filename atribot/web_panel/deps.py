"""面板共享基础设施：鉴权与 DI 辅助、日志环形缓冲、配置文件读写工具

各功能域路由按页面拆分在 routes/ 包内，此处只放被多个模块共用的东西。
所有服务依赖均为惰性获取（请求内从 DI 容器解析），
使面板可以在不完整的运行环境中安全导入与独立调试。
"""

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

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atribot.core.service_container import container

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


def _access_token() -> Optional[str]:
    """面板访问令牌:web_panel.access_token > 环境变量 ATRI_PANEL_TOKEN > 第一个平台的 access_token"""
    try:
        cfg = _cfg()
        raw = cfg._raw_config
    except Exception:
        return os.environ.get("ATRI_PANEL_TOKEN") or None
    token = (raw.get("web_panel") or {}).get("access_token") or os.environ.get("ATRI_PANEL_TOKEN")
    if not token:
        for platform in (raw.get("platforms") or {}).values():
            if isinstance(platform, dict) and platform.get("access_token"):
                token = platform["access_token"]
                break
    return token or None


_security = HTTPBearer(auto_error=False)


# ---------- 登录防暴力破解：按 IP 记录连续失败，平方递增锁定 ----------
# 第 n 次连续失败后锁定该 IP 60*n² 秒（封顶 24 小时），登录成功即清零。
# 只取 request.client.host，不信任 X-Forwarded-For（可被伪造绕过锁定）；
# 将来若挂反向代理暴露面板，需改为从代理头取真实客户端 IP。

_AUTH_INITIAL_LOCKOUT = 60  # 首次失败锁定秒数
_AUTH_LOCKOUT_MAX = 86400  # 锁定上限（24 小时）

_auth_failures: dict = {}  # IP -> 连续失败时间戳列表（time.monotonic()）
_auth_failures_lock = Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _lockout_seconds(fails: int) -> int:
    return min(_AUTH_INITIAL_LOCKOUT * fails * fails, _AUTH_LOCKOUT_MAX)


def _auth_rate_limited(ip: str) -> Optional[float]:
    """该 IP 是否处于锁定期，是则返回剩余秒数，否则 None"""
    with _auth_failures_lock:
        stamps = _auth_failures.get(ip)
        if not stamps:
            return None
        remaining = _lockout_seconds(len(stamps)) - (time.monotonic() - stamps[-1])
        return remaining if remaining > 0 else None


def _register_auth_failure(ip: str) -> None:
    with _auth_failures_lock:
        now = time.monotonic()
        _auth_failures.setdefault(ip, []).append(now)
        # 清扫超过 24 小时无失败的 IP（其锁定期必然已过），防内存无限增长
        for stale in [k for k, v in _auth_failures.items() if now - v[-1] > _AUTH_LOCKOUT_MAX]:
            del _auth_failures[stale]


def _clear_auth_failures(ip: str) -> None:
    with _auth_failures_lock:
        _auth_failures.pop(ip, None)


async def _auth(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    token = _access_token()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="未配置访问令牌：请在 config.json 添加 web_panel.access_token 或设置环境变量 ATRI_PANEL_TOKEN",
        )
    ip = _client_ip(request)
    # 先验令牌：正确令牌立即放行并清零失败计数（即使处于锁定期），
    # 锁定只针对错误猜测——攻击者拿不到正确令牌，放行不损失防爆破强度
    if creds is not None and secrets.compare_digest(
        creds.credentials.encode("utf-8"), token.encode("utf-8")
    ):
        _clear_auth_failures(ip)
        return
    remaining = _auth_rate_limited(ip)
    if remaining is not None:
        # 锁定期内的错误令牌：直接拒绝且不再计数，避免持续探测把锁无限续期
        raise HTTPException(
            status_code=429,
            detail=f"尝试次数过多，请 {int(remaining) + 1} 秒后重试",
            headers={"Retry-After": str(int(remaining) + 1)},
        )
    _register_auth_failure(ip)
    raise HTTPException(status_code=401, detail="Unauthorized")


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


def _save_config_file(path, content: str, validate=None) -> str:
    """解析 + 校验 + 备份 + 写入，返回备份路径"""
    parsed = _parse_json_or_400(content)
    if validate:
        validate(parsed)
    backup = _backup_file(path)
    _write_json(path, parsed)
    return str(backup)


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
