"""面板共享基础设施：鉴权与 DI 辅助、日志环形缓冲、配置文件读写工具

各功能域路由按页面拆分在 routes/ 包内，此处只放被多个模块共用的东西。
所有服务依赖均为惰性获取（请求内从 DI 容器解析），
使面板可以在不完整的运行环境中安全导入与独立调试。
"""

import json
import logging
import os
import shutil
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import Depends, HTTPException
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


async def _auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    token = _access_token()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="未配置访问令牌：请在 config.json 添加 web_panel.access_token 或设置环境变量 ATRI_PANEL_TOKEN",
        )
    if creds is None or creds.credentials != token:
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
