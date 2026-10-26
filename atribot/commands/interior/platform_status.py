"""平台适配器状态报告格式化

纯格式化逻辑，不依赖服务容器，便于单测与复用。
"""

from datetime import datetime
from typing import Any, Mapping

from atribot.core.atri_config import (
    HttpAdapterConfig,
    PlatformInstanceConfig,
    WebSocketClientConfig,
    WebSocketServerConfig,
)
from atribot.core.platform import get_adapter_class
from atribot.core.platform.base import PlatformAdapter

CONNECTION_LABELS: dict[str, str] = {
    "WebSocket_client": "WebSocket 客户端（Bot 主动连接）",
    "WebSocket_server": "WebSocket 服务端（等待客户端接入）",
    "http": "HTTP（上报 + 调用）",
}
"""连接类型 → 展示文案"""


def connection_label(connection_type: str) -> str:
    """返回连接类型的展示文案"""
    return CONNECTION_LABELS.get(connection_type, "未知连接方式")


def resolve_ws_path(cfg: WebSocketClientConfig) -> str:
    """复现适配器的 WS 路径解析规则

    优先级：配置 `ws_path` → 适配器类默认路径 → OneBot 的 `/websocket`；
    都未命中且未配置令牌时使用根路径 `/`。
    """
    path = cfg.ws_path
    if not path:
        adapter_cls = get_adapter_class(cfg.adapter)
        path = getattr(adapter_cls, "_default_ws_path", None) if adapter_cls else None
    if path:
        return "/" + str(path).strip("/")
    return "/websocket" if cfg.access_token else "/"


def endpoint_of(cfg: PlatformInstanceConfig) -> str:
    """返回平台的目标/监听地址（不含令牌）"""
    if isinstance(cfg, WebSocketClientConfig):
        return f"ws://{cfg.url}{resolve_ws_path(cfg)}"
    if isinstance(cfg, WebSocketServerConfig):
        return f"ws://{cfg.host}:{cfg.port}"
    return f"http://{cfg.url or f'{cfg.host}:{cfg.port}'}"


def port_of(cfg: PlatformInstanceConfig) -> str:
    """返回平台使用的端口（客户端模式从 url 解析，服务端模式取监听端口）"""
    if isinstance(cfg, (WebSocketServerConfig, HttpAdapterConfig)):
        return str(cfg.port)
    _, _, port = str(cfg.url or "").rpartition(":")
    return port if port.isdigit() else "-"


def token_label(configured: bool) -> str:
    """访问令牌展示文案（只说明是否存在，不输出内容）"""
    return "已配置" if configured else "未配置"


def runtime_state(info: Mapping[str, Any]) -> str:
    """根据运行时状态快照生成状态标签"""
    if info.get("is_connected"):
        return "✅ 已连接"
    if info.get("is_started") or info.get("is_running"):
        return "🟡 已启动（连接中）"
    return "❌ 未启动"


def _config_lines(cfg: PlatformInstanceConfig) -> list[str]:
    """平台配置的公共展示行"""
    return [
        f"    连接方式：{cfg.connection_type}（{connection_label(cfg.connection_type)}）",
        f"    目标地址：{endpoint_of(cfg)}",
        f"    端口：{port_of(cfg)}",
        f"    访问令牌：{token_label(bool(cfg.access_token))}",
    ]


def build_platform_report(
    *,
    instances: Mapping[str, PlatformInstanceConfig],
    adapters: Mapping[str, PlatformAdapter],
    registered: Mapping[str, type[PlatformAdapter]],
    manager_running: bool,
    manager_available: bool = True,
    queue_stats: Mapping[str, int] | None = None,
    now: datetime | None = None,
) -> str:
    """生成平台适配器状态报告

    Args:
        instances: config.platforms 中的全部平台配置（含已禁用）
        adapters: PlatformManager 中已创建的运行时适配器
        registered: 已注册的适配器类型表
        manager_running: PlatformManager 是否已启动适配器与 EventBus
        manager_available: PlatformManager 是否可用（未注册时为 False）
        queue_stats: MessageQueue.stats() 快照，None 表示不展示队列信息
        now: 报告时间，默认取当前时间

    Returns:
        可直接作为合并转发内容发送的多行文本
    """
    lines: list[str] = ["🔌 平台适配器状态"]
    lines.append(f"查询时间：{(now or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}")

    connected = sum(1 for adapter in adapters.values() if adapter.is_connected)
    if manager_available:
        state = "运行中" if manager_running else "未运行"
    else:
        state = "不可用（未注册）"
    lines.append(f"管理器状态：{state} · 运行时适配器 {len(adapters)} 个（已连接 {connected} 个）")

    lines.append("")
    lines.append(f"━━ 运行时适配器（{len(adapters)}）━━")
    if adapters:
        for index, (name, adapter) in enumerate(adapters.items(), start=1):
            info = adapter.get_connection_info()
            cfg = instances.get(name)
            lines.append(f"[{index}] {name}  {runtime_state(info)}")
            adapter_type = cfg.adapter if cfg else "?"
            lines.append(f"    适配器类型：{adapter_type}（{type(adapter).__name__}）")
            lines.append(f"    来源标识：{adapter.source_name}")
            if cfg is not None:
                lines.extend(_config_lines(cfg))
            retry_count = info.get("retry_count")
            if retry_count is not None:
                lines.append(f"    重连次数：{retry_count}")
    else:
        lines.append("  （无，请检查 config.platforms 配置）")

    pending = [(name, cfg) for name, cfg in instances.items() if name not in adapters]
    if pending:
        lines.append("")
        lines.append(f"━━ 配置未生效的平台（{len(pending)}）━━")
        for index, (name, cfg) in enumerate(pending, start=1):
            if not cfg.enabled:
                reason = "⚪ 已禁用（enabled=false）"
            elif not cfg.adapter:
                reason = "⚪ 未创建（未指定 adapter）"
            elif cfg.adapter not in registered:
                reason = "⚪ 未创建（适配器类型未注册）"
            else:
                reason = "⚪ 未创建（初始化失败，详见日志）"
            lines.append(f"[{index}] {name}  {reason}")
            lines.append(f"    适配器类型：{cfg.adapter or '未指定'}")
            lines.extend(_config_lines(cfg))

    lines.append("")
    lines.append(f"━━ 已注册适配器类型（{len(registered)}）━━")
    if registered:
        for name, adapter_cls in sorted(registered.items()):
            used = sum(1 for cfg in instances.values() if cfg.adapter == name)
            lines.append(f"  {name} → {adapter_cls.__name__}（配置引用 {used} 次）")
    else:
        lines.append("  （无）")

    if queue_stats is not None:
        lines.append("")
        lines.append("━━ 消息队列 ━━")
        lines.append(f"  队列深度：{queue_stats.get('depth', 0)} / {queue_stats.get('maxsize', 0)}")
        lines.append(f"  累计入队：{queue_stats.get('total_pushed', 0)}")
        lines.append(
            "  溢出 {overflow} · 丢弃 {dropped} · 过期 {stale}".format(
                overflow=queue_stats.get("overflow_count", 0),
                dropped=queue_stats.get("dropped_count", 0),
                stale=queue_stats.get("stale_dropped", 0),
            )
        )

    return "\n".join(lines)
