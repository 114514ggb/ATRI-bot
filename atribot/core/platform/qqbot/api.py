"""QQ 官方机器人 HTTP API 客户端

覆盖适配器用到的最小接口集合：

- ``GET  /gateway/bot``                                   获取 WebSocket 网关地址
- ``GET  /users/@me``                                     获取机器人自身账号信息
- ``POST /v2/groups/{group_openid}/messages``             发送群消息
- ``POST /v2/users/{openid}/messages``                    发送 C2C 消息
- ``POST /v2/groups/{group_openid}/files``                上传群富媒体
- ``POST /v2/users/{openid}/files``                       上传 C2C 富媒体
- ``DELETE /v2/groups/{group_openid}/messages/{id}``      撤回群消息
"""

from __future__ import annotations

import asyncio
import json
from logging import Logger
from typing import Any

import aiohttp

from atribot.core.logger import get_named_logger
from atribot.core.platform.qqbot.auth import QQBotTokenManager


class QQBotAPIError(RuntimeError):
    """QQ 官方接口返回错误"""

    def __init__(self, action: str, status: int, payload: Any) -> None:
        self.action = action
        self.status = status
        self.payload = payload
        detail = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        super().__init__(f"QQ 官方接口 {action} 失败 (status={status}): {detail[:300]}")


class QQBotApiClient:
    """QQ 官方机器人 HTTP 客户端（自动携带鉴权头、401 重试一次）"""

    PRODUCTION_BASE = "https://api.sgroup.qq.com"
    SANDBOX_BASE = "https://sandbox.api.sgroup.qq.com"

    def __init__(
        self,
        token_manager: QQBotTokenManager,
        *,
        sandbox: bool = False,
        log: Logger | None = None,
        timeout: float = 20.0,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._tokens = token_manager
        self.log = log or get_named_logger("QQBotAPI")
        self.base_url = self.SANDBOX_BASE if sandbox else self.PRODUCTION_BASE
        self._timeout = timeout
        self._session = session

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            )
        return self._session

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """发起带鉴权的 API 请求

        Args:
            method: HTTP 方法
            path: 以 ``/`` 开头的路径
            json_body: JSON 请求体
            retry_auth: 401 时是否作废 token 后重试一次

        Returns:
            响应 JSON 字典（可能为空字典）

        Raises:
            QQBotAPIError: 接口返回非 2xx 或业务错误码
        """
        session = self._ensure_session()
        headers = await self._tokens.auth_headers()
        url = f"{self.base_url}{path}"
        action = f"{method} {path}"

        try:
            async with session.request(
                method, url, json=json_body, headers=headers
            ) as response:
                status = response.status
                text = await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise QQBotAPIError(action, 0, f"网络异常: {exc}") from exc

        if status == 401 and retry_auth:
            self.log.warning("QQ 官方接口返回 401，刷新 token 后重试: %s", action)
            self._tokens.invalidate()
            return await self.request(
                method, path, json_body=json_body, retry_auth=False
            )

        data: Any = {}
        if text:
            try:
                data = json.loads(text)
            except ValueError:
                data = text

        if status >= 400:
            raise QQBotAPIError(action, status, data)

        if isinstance(data, dict):
            code = data.get("code")
            if code not in (None, 0) and "message" in data:
                raise QQBotAPIError(action, status, data)
            return data

        if isinstance(data, list):
            return {"data": data}
        return {}

    async def get_gateway_url(self) -> str:
        """获取 WebSocket 网关地址"""
        data = await self.request("GET", "/gateway/bot")
        url = data.get("url")
        if not url:
            raise QQBotAPIError("GET /gateway/bot", 200, data)
        return str(url)

    async def get_me(self) -> dict[str, Any]:
        """获取机器人自身账号信息"""
        return await self.request("GET", "/users/@me")

    async def send_group_message(
        self, group_openid: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """发送群消息"""
        return await self.request(
            "POST",
            f"/v2/groups/{group_openid}/messages",
            json_body=payload,
        )

    async def send_c2c_message(
        self, openid: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """发送 C2C 私聊消息"""
        return await self.request(
            "POST",
            f"/v2/users/{openid}/messages",
            json_body=payload,
        )

    async def upload_group_media(
        self,
        group_openid: str,
        file_type: int,
        *,
        url: str | None = None,
        file_data: str | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """上传群富媒体，返回 ``{"file_info": ...}``"""
        payload: dict[str, Any] = {
            "file_type": file_type,
            "srv_send_msg": False,
        }
        if url:
            payload["url"] = url
        if file_data:
            payload["file_data"] = file_data
        if file_name:
            payload["file_name"] = file_name

        data = await self.request(
            "POST",
            f"/v2/groups/{group_openid}/files",
            json_body=payload,
        )
        return self._extract_media(data, "POST /v2/groups/{group_openid}/files")

    async def upload_c2c_media(
        self,
        openid: str,
        file_type: int,
        *,
        url: str | None = None,
        file_data: str | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """上传 C2C 富媒体，返回 ``{"file_info": ...}``"""
        payload: dict[str, Any] = {
            "file_type": file_type,
            "srv_send_msg": False,
        }
        if url:
            payload["url"] = url
        if file_data:
            payload["file_data"] = file_data
        if file_name:
            payload["file_name"] = file_name

        data = await self.request(
            "POST",
            f"/v2/users/{openid}/files",
            json_body=payload,
        )
        return self._extract_media(data, "POST /v2/users/{openid}/files")

    @staticmethod
    def _extract_media(data: dict[str, Any], action: str) -> dict[str, Any]:
        file_info = data.get("file_info")
        if not file_info:
            raise QQBotAPIError(action, 200, data)
        return {"file_info": file_info}

    async def delete_group_message(
        self, group_openid: str, message_id: str
    ) -> dict[str, Any]:
        """撤回群消息"""
        return await self.request(
            "DELETE",
            f"/v2/groups/{group_openid}/messages/{message_id}",
        )

    async def download(self, url: str, *, max_bytes: int = 20 * 1024 * 1024) -> bytes | None:
        """下载远程资源（用于把网络图片转成 base64 上传）"""
        session = self._ensure_session()
        try:
            async with session.get(url) as response:
                if response.status >= 400:
                    self.log.warning("下载媒体失败 (status=%s): %s", response.status, url)
                    return None
                data = await response.content.read(max_bytes + 1)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            self.log.warning("下载媒体异常: %s (%s)", exc, url)
            return None

        if len(data) > max_bytes:
            self.log.warning("媒体超过大小上限 %d 字节，已丢弃: %s", max_bytes, url)
            return None
        return data

    async def close(self) -> None:
        """关闭内部 HTTP 会话"""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
