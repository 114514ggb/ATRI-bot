"""统一 HTTP 客户端。

通过单例 aiohttp.ClientSession + TCPConnector 复用 TCP 连接，
避免在各模块中反复创建临时 Session 导致的资源浪费与连接泄漏。

使用方式：
    from atribot.core.service_container import container
    http = container.get("HTTPClient")
    data = await http.get_bytes("https://example.com/image.jpg")
    result = await http.post_json("https://api.example.com/v1", {"key": "value"})
"""

import asyncio
from typing import Any

import aiohttp
from aiohttp.resolver import AsyncResolver

_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "QQ/9.9.27-45758 CFNetwork/1220.1 Darwin/20.3.0",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class HTTPClient:
    """统一 HTTP 客户端，复用单一 TCP 连接池。

    默认 headers 为 QQ 客户端 UA,各调用方可通过 headers 参数按需覆盖或追加
    """

    def __init__(self) -> None:
        connector = aiohttp.TCPConnector(
            limit=100, 
            keepalive_timeout=30,
            resolver=AsyncResolver(
                nameservers=['8.8.8.8', '8.8.4.4', '114.114.114.114'] #DNS相关
            )
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            headers=_DEFAULT_HEADERS,
            timeout=_DEFAULT_TIMEOUT,
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        """暴露底层 Session,供需要精细控制的调用方使用(如流式读取、Range请求等)"""
        return self._session

    async def get_bytes(
        self,
        url: str,
        max_bytes: int | None = None,
        *,
        headers: dict[str, str] | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> bytes:
        """GET 请求，读取响应体为 bytes,支持大小上限

        Args:
            url: 目标 URL。
            max_bytes: 最大允许读取的字节数,None 表示不限制。
            headers: 可选的请求头，会与 Session 默认 headers 合并。
            timeout: 可选的超时配置，覆盖 Session 默认超时。

        Returns:
            响应体的 bytes。

        Raises:
            ValueError: HTTP 状态码非 2xx 或超过 max_bytes 时抛出。
        """
        try:
            async with self._session.get(url, headers=headers, timeout=timeout) as resp:
                if not (200 <= resp.status < 300):
                    raise ValueError(f"下载失败，状态码: {resp.status}")
                if max_bytes is None:
                    return await resp.read()
                data = await resp.content.read(max_bytes + 1)
                if len(data) > max_bytes:
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
        """POST 表单数据（application/x-www-form-urlencoded）返回 JSON 响应

        Args:
            url: 目标 URL。
            data: 表单字段字典。
            headers: 可选的额外请求头。

        Returns:
            解析后的 JSON 响应（dict/list）。
        """
        async with self._session.post(url, data=data, headers=headers) as resp:
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
            headers: 可选的额外请求头（如 Authorization）。
            timeout: 可选的超时配置。

        Returns:
            解析后的 JSON 响应（dict/list）。
        """
        async with self._session.post(
            url, json=payload, headers=headers, timeout=timeout
        ) as resp:
            return await resp.json()

    async def close(self) -> None:
        """释放连接池资源。"""
        if not self._session.closed:
            await self._session.close()
