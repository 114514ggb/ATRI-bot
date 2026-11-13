"""统一异步 HTTP 客户端。

单例 aiohttp.ClientSession + TCPConnector 复用连接池，避免各模块重复创建 Session。
解析器 / 代理 / 超时由顶层 ``config.network`` 统一控制（见 ``net_utils.create_session``）。

使用方式：
    from atribot.core.service_container import container
    http = container.get("HTTPClient")
    data = await http.get_bytes("https://example.com/image.jpg")
    result = await http.post_json("https://api.example.com/v1", {"key": "value"})
"""

import asyncio
import logging
from typing import Any

import aiohttp

from atribot.common_utils.net_utils import (
    create_session,
    create_tcp_connector,
    effective_dns_mode,
    get_network_config,
    resolve_proxy,
    set_resolver_mode_override,
)
from atribot.core.atri_config import atriConfig

log = logging.getLogger("atri-bot.HTTPClient")

_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "QQ/9.9.27-45758 CFNetwork/1220.1 Darwin/20.3.0",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


class HTTPClient:
    """统一 HTTP 客户端，复用单一 TCP 连接池，默认 QQ UA headers。"""

    def __init__(self, config: atriConfig) -> None:
        self._session = self._build_session()
        self._unsubscribe = config.on_change("network", self.reload_network)

    def _build_session(self) -> aiohttp.ClientSession:
        """按当前 network 配置创建会话（新连接池）"""
        return create_session(
            connector=create_tcp_connector(), headers=_DEFAULT_HEADERS
        )

    async def reload_network(self, _value: Any = None) -> None:
        """network 段变更后重建连接池（仅 HTTPClient 支持热生效）

        先创建新会话再关闭旧会话，尽量不打断在途请求。
        """
        set_resolver_mode_override(None)
        old_session = self._session
        self._session = self._build_session()
        try:
            await old_session.close()
        except Exception:
            log.debug("关闭旧 HTTP 会话时出现异常", exc_info=True)
        log.info(
            "HTTPClient 已按 network 配置重建连接池 (dns_mode=%s, proxy=%s)",
            effective_dns_mode(),
            get_network_config().proxy or "未启用",
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        """暴露底层 ClientSession，供需要精细控制的调用方使用（如 Range/流式请求）。"""
        return self._session

    async def get_bytes(
        self,
        url: str,
        max_bytes: int | None = None,
        *,
        headers: dict[str, str] | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> bytes:
        """GET 请求，读取响应体为 bytes，支持大小上限与 Content-Length 完整性校验。

        Args:
            url: 目标 URL。
            max_bytes: 最大字节数，None 表示不限制。
            headers/timeout: 可选，覆盖 Session 默认值。

        Raises:
            ValueError: 状态码非 2xx、下载不完整或超过 max_bytes 时抛出。
        """
        try:
            async with self._session.get(
                url, headers=headers, timeout=timeout, proxy=resolve_proxy(url)
            ) as resp:
                if not (200 <= resp.status < 300):
                    raise ValueError(f"下载失败，状态码: {resp.status}")
                data = await resp.read()
                clen = resp.headers.get("Content-Length")
                if clen and not resp.headers.get("Content-Encoding"):
                    try:
                        expected = int(clen)
                    except (TypeError, ValueError):
                        expected = None
                    if expected is not None and len(data) != expected:
                        raise ValueError(
                            f"下载不完整: Content-Length={clen} 实际={len(data)} bytes"
                        )
                if max_bytes is not None and len(data) > max_bytes:
                    raise ValueError(f"下载文件超过大小限制 ({max_bytes} bytes)")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            raise ValueError(f"请求失败: {error}") from error
        
    async def post_form(
        self,
        url: str,
        data: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """POST 表单数据（application/x-www-form-urlencoded），返回 JSON 响应。

        Args:
            url: 目标 URL。
            data: 表单字段字典。
            headers: 可选额外请求头。

        Returns:
            解析后的 JSON 响应（dict/list）。
        """
        async with self._session.post(
            url, data=data, headers=headers, proxy=resolve_proxy(url)
        ) as resp:
            return await resp.json()

    async def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> Any:
        """POST JSON 数据，返回 JSON 响应。

        Args:
            url: 目标 URL。
            payload: 请求体字典，自动序列化为 JSON。
            headers: 可选额外请求头。
            timeout: 可选超时配置。

        Returns:
            解析后的 JSON 响应（dict/list）。
        """
        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
            proxy=resolve_proxy(url),
        ) as resp:
            return await resp.json()

    async def close(self) -> None:
        """释放连接池资源。"""
        self._unsubscribe()
        if not self._session.closed:
            await self._session.close()
