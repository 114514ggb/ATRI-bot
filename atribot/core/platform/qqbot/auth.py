"""QQ 官方机器人 Access Token 管理

官方鉴权流程（API v2）::

    POST https://bots.qq.com/app/getAppAccessToken
    {"appId": "<app_id>", "clientSecret": "<app_secret>"}
    -> {"access_token": "...", "expires_in": "7200"}

后续请求带 ``Authorization: QQBot {access_token}`` 与 ``X-Union-Appid: {app_id}``。
"""

from __future__ import annotations

import asyncio
import json
import time
from logging import Logger
from typing import Any

import aiohttp

from atribot.common_utils.net_utils import (
    DNS_HINT,
    create_session,
    is_dns_error,
    resolve_proxy,
)
from atribot.core.logger import get_named_logger


class QQBotAuthError(RuntimeError):
    """获取或刷新 Access Token 失败"""


class QQBotTokenManager:
    """Access Token 获取与自动刷新"""

    TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        *,
        log: Logger | None = None,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 20.0,
        refresh_margin: float = 60.0,
        token_url: str | None = None,
    ) -> None:
        if not app_id or not app_secret:
            raise QQBotAuthError("QQ 官方机器人缺少 app_id / app_secret 配置")

        self.app_id = app_id
        self._app_secret = app_secret
        self.log = log or get_named_logger("QQBotToken")
        self._timeout = timeout
        self._refresh_margin = refresh_margin
        self._token_url = token_url or self.TOKEN_URL

        self._session = session
        self._owns_session = session is None
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expire_at: float = 0.0

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = create_session(
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            )
            self._owns_session = True
        return self._session

    async def get_token(self) -> str:
        """获取有效 Access Token（临近过期时自动刷新）"""
        if self._token and time.time() < self._expire_at - self._refresh_margin:
            return self._token

        async with self._lock:
            if self._token and time.time() < self._expire_at - self._refresh_margin:
                return self._token
            await self._refresh()
            if self._token is None:
                raise QQBotAuthError("QQ 官方机器人 Access Token 为空")
            return self._token

    async def auth_headers(self) -> dict[str, str]:
        """构建带鉴权的请求头"""
        token = await self.get_token()
        return {
            "Authorization": f"QQBot {token}",
            "X-Union-Appid": self.app_id,
        }

    def invalidate(self) -> None:
        """作废当前 token（收到 401 时调用，下一次请求会重新获取）"""
        self._token = None
        self._expire_at = 0.0

    async def _refresh(self) -> None:
        session = self._ensure_session()
        payload: dict[str, Any] = {
            "appId": self.app_id,
            "clientSecret": self._app_secret,
        }
        self.log.debug("正在获取 QQ 官方机器人 Access Token (app_id=%s)", self.app_id)
        try:
            async with session.post(
                self._token_url, json=payload, proxy=resolve_proxy(self._token_url)
            ) as response:
                text = await response.text()
                status = response.status
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            message = f"获取 Access Token 网络异常: {exc}"
            if is_dns_error(exc):
                message = f"{message}｜{DNS_HINT}"
            raise QQBotAuthError(message) from exc

        try:
            data: Any = json.loads(text) if text else {}
        except ValueError as exc:
            raise QQBotAuthError(f"获取 Access Token 响应非 JSON (status={status}): {text[:200]}") from exc

        if status >= 400 or not isinstance(data, dict):
            raise QQBotAuthError(f"获取 Access Token 失败 (status={status}): {text[:200]}")

        token = data.get("access_token")
        expires_in_raw = data.get("expires_in")
        if not token or expires_in_raw is None:
            raise QQBotAuthError(f"获取 Access Token 失败，响应缺少字段: {data}")

        try:
            expires_in = float(expires_in_raw)
        except (TypeError, ValueError):
            expires_in = 7200.0

        self._token = str(token)
        self._expire_at = time.time() + max(expires_in, 120.0)
        self.log.info("QQ 官方机器人 Access Token 已更新（有效期 %.0fs）", expires_in)

    async def close(self) -> None:
        """关闭内部 HTTP 会话"""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
