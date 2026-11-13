"""网络工具：端口探测 + 统一的 aiohttp 解析器 / Session 工厂

关于 DNS:aiohttp 在检测到已安装 ``aiodns`` 时会默认使用 c-ares
（``AsyncResolver``）。c-ares 在 Windows / VPN / 多网卡 / WSL 等环境下可能
读不到可用的 nameserver，直接报 ``Could not contact DNS servers``。
本模块默认改用系统解析器（``ThreadedResolver``，底层 getaddrinfo），
并允许通过顶层 ``config.network`` 指定 DNS 服务器或代理。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import sys
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlsplit

import aiohttp
from aiohttp import resolver as aiohttp_resolver
from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.resolver import AsyncResolver, ThreadedResolver

if TYPE_CHECKING:
    from atribot.core.atri_config import NetworkConfig

log = logging.getLogger("atri-bot.Network")

_DNS_ERROR_MARKERS = (
    "could not contact dns servers",
    "temporary failure in name resolution",
    "name or service not known",
    "nodename nor servname provided",
    "getaddrinfo failed",
    "no address associated with hostname",
)
"""异常文本中可判定为 DNS 解析失败的片段"""

DNS_HINT = (
    "DNS 解析失败：可在 assets/config.json 顶层 network 段指定 DNS 服务器，例如 "
    '{"dns_mode": "custom", "dns_nameservers": ["223.5.5.5", "119.29.29.29"]}；'
    "默认 dns_mode=system 使用系统 DNS"
)
"""DNS 解析失败时给用户的配置建议"""

_resolver_mode_override: str | None = None
"""运行时解析器模式覆盖（启动自检降级 / 热重载后重新评估时设置）"""


class _LazyResolver(AbstractResolver):
    """惰性解析器包装：底层解析器在首次解析时才创建

    aiohttp 的 ``ThreadedResolver`` 与 ``AsyncResolver`` 在构造时需要运行中的
    事件循环，惰性创建可以让 ``create_session`` / ``create_tcp_connector``
    在同步上下文中也能安全调用。
    """

    def __init__(self, factory: Callable[[], AbstractResolver]) -> None:
        self._factory = factory
        self._resolver: AbstractResolver | None = None

    def _ensure(self) -> AbstractResolver:
        if self._resolver is None:
            self._resolver = self._factory()
        return self._resolver

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        return await self._ensure().resolve(host, port, family=family)

    async def close(self) -> None:
        resolver, self._resolver = self._resolver, None
        if resolver is not None:
            await resolver.close()


def try_bind_port(host: str, port: int) -> socket.socket | None:
    """尝试绑定 (host, port)，成功返回已绑定的 socket,端口被占用等失败返回 None

    返回的 socket 已绑定但未监听，可直接交给 asyncio/uvicorn 的
    serve(sockets=[...]) 使用（所有权随之转移，由其负责关闭）
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except (OSError, OverflowError):
        sock.close()
        return None
    return sock


def is_port_in_use(host: str, port: int) -> bool:
    """探测 (host, port) 是否已被占用（探测后立即释放，不占住端口）"""
    sock = try_bind_port(host, port)
    if sock is None:
        return True
    sock.close()
    return False


def bind_port_with_fallback(
    host: str, port: int, max_attempts: int = 10
) -> tuple[socket.socket, int] | None:
    """从 port 起尝试绑定，被占用则自动 +1 递增，最多 max_attempts 次

    成功返回 (已绑定的 socket, 实际端口)，失败返回 None
    """
    for candidate in range(port, port + max_attempts):
        sock = try_bind_port(host, candidate)
        if sock is not None:
            return sock, sock.getsockname()[1]
    return None


def get_network_config() -> "NetworkConfig":
    """读取当前生效的网络配置（容器未就绪时返回默认值）"""
    from atribot.core.atri_config import NetworkConfig, atriConfig

    try:
        from atribot.core.service_container import container

        return container.get_by_type(atriConfig).network
    except Exception:
        return NetworkConfig()


def effective_dns_mode() -> str:
    """当前生效的解析器模式（自检降级可临时覆盖配置值）"""
    if _resolver_mode_override:
        return _resolver_mode_override
    return get_network_config().dns_mode


def set_resolver_mode_override(mode: str | None) -> None:
    """设置进程内解析器模式覆盖，传 None 取消覆盖"""
    global _resolver_mode_override
    _resolver_mode_override = mode


def build_resolver(mode: str | None = None) -> AbstractResolver | None:
    """按配置构建 aiohttp 解析器

    返回 None 表示交给 aiohttp 选择默认解析器（``cares`` 模式）。

    Args:
        mode: 显式指定模式，缺省使用当前生效配置

    Returns:
        AbstractResolver | None: 解析器实例
    """
    target = mode or effective_dns_mode()
    if target == "custom":
        nameservers = get_network_config().dns_nameservers
        if not nameservers:
            log.warning("network.dns_mode=custom 但 dns_nameservers 为空，回退系统 DNS")
            return _LazyResolver(ThreadedResolver)
        if not aiohttp_resolver.aiodns_default:
            log.warning("aiodns 不可用，network.dns_mode=custom 回退系统 DNS")
            return _LazyResolver(ThreadedResolver)
        return _LazyResolver(lambda: AsyncResolver(nameservers=list(nameservers)))
    if target == "cares":
        return None
    return _LazyResolver(ThreadedResolver)


def create_tcp_connector(**kwargs: Any) -> aiohttp.TCPConnector:
    """创建带统一解析器配置的 TCPConnector

    Args:
        **kwargs: 其余参数透传给 ``aiohttp.TCPConnector``

    Returns:
        aiohttp.TCPConnector: 连接器实例
    """
    kwargs.setdefault("limit", 100)
    kwargs.setdefault("keepalive_timeout", 30)
    resolver = build_resolver()
    if resolver is not None:
        kwargs["resolver"] = resolver
    return aiohttp.TCPConnector(**kwargs)


def create_session(
    *,
    headers: dict[str, str] | None = None,
    timeout: aiohttp.ClientTimeout | None = None,
    connector: aiohttp.BaseConnector | None = None,
) -> aiohttp.ClientSession:
    """创建统一配置的 aiohttp 会话（解析器 / 环境变量代理 / 超时）

    Args:
        headers: 默认请求头
        timeout: 超时配置；缺省取 network 的 total_timeout / connect_timeout
        connector: 自定义连接器；缺省由 :func:`create_tcp_connector` 创建

    Returns:
        aiohttp.ClientSession: 会话实例
    """
    config = get_network_config()
    if connector is None:
        connector = create_tcp_connector()
    if timeout is None:
        timeout = aiohttp.ClientTimeout(
            total=config.total_timeout, connect=config.connect_timeout
        )
    return aiohttp.ClientSession(
        connector=connector,
        headers=headers,
        timeout=timeout,
        trust_env=config.trust_env,
    )


def resolve_proxy(url: str) -> str | None:
    """按 network 配置决定某个 URL 是否走代理

    ``proxy_bypass`` 中的条目按「主机名完全相等」或「域名后缀」匹配。

    Args:
        url: 目标 URL

    Returns:
        str | None: 代理地址；None 表示直连
    """
    config = get_network_config()
    proxy = (config.proxy or "").strip()
    if not proxy:
        return None
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return proxy
    for pattern in config.proxy_bypass:
        suffix = pattern.strip().lower().lstrip(".")
        if suffix and (host == suffix or host.endswith(f".{suffix}")):
            return None
    return proxy


def _looks_like_dns_error(exc: BaseException) -> bool:
    """单个异常本身是否表示 DNS 解析失败"""
    if isinstance(exc, socket.gaierror):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in _DNS_ERROR_MARKERS)


def is_dns_error(exc: BaseException | None) -> bool:
    """判断异常（含 __cause__ / __context__ / aiohttp os_error）是否由 DNS 解析失败引起"""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _looks_like_dns_error(current):
            return True
        os_error = getattr(current, "os_error", None)
        if isinstance(os_error, BaseException) and _looks_like_dns_error(os_error):
            return True
        current = current.__cause__ or current.__context__
    return False


async def _probe_host(resolver: AbstractResolver, host: str, timeout: float) -> bool:
    """用指定解析器解析单个主机（成功与否）"""
    try:
        infos = await asyncio.wait_for(
            resolver.resolve(host, 443, family=socket.AF_INET), timeout
        )
    except Exception as exc:
        log.debug("DNS 自检解析失败 %s: %s", host, exc)
        return False
    return bool(infos)


async def _probe_hosts(hosts: list[str], mode: str, timeout: float) -> dict[str, bool]:
    """用指定模式并发探测多个主机"""
    resolver = build_resolver(mode)
    if resolver is None:
        resolver = aiohttp_resolver.DefaultResolver()
    try:
        results = await asyncio.gather(
            *(_probe_host(resolver, host, timeout) for host in hosts)
        )
    finally:
        close = getattr(resolver, "close", None)
        if callable(close):
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                log.debug("关闭 DNS 解析器失败", exc_info=True)
    return dict(zip(hosts, results))


async def diagnose_network(timeout: float = 3.0) -> bool:
    """启动期 DNS 自检：探测关键域名，失败时尝试降级为系统 DNS

    只做诊断与降级，不阻断启动。

    Args:
        timeout: 单个域名解析超时（秒）

    Returns:
        bool: 是否至少有一种解析方式可用
    """
    config = get_network_config()
    hosts = list(config.probe_hosts) or ["bots.qq.com"]
    mode = effective_dns_mode()
    results = await _probe_hosts(hosts, mode, timeout)
    summary = ", ".join(
        f"{host}={'ok' if ok else 'fail'}" for host, ok in results.items()
    )
    if all(results.values()):
        log.info("DNS 自检通过 (dns_mode=%s): %s", mode, summary)
        return True

    if mode != "system":
        fallback = await _probe_hosts(hosts, "system", timeout)
        fallback_summary = ", ".join(
            f"{host}={'ok' if ok else 'fail'}" for host, ok in fallback.items()
        )
        if all(fallback.values()):
            set_resolver_mode_override("system")
            log.warning(
                "DNS 自检：dns_mode=%s 解析失败（%s），已临时降级为 system（%s）",
                mode,
                summary,
                fallback_summary,
            )
            return True

    log.warning("DNS 自检失败 (dns_mode=%s): %s | %s", mode, summary, DNS_HINT)
    return False
