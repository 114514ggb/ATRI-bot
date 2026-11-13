"""QQ 官方机器人平台适配器

连接方式：QQ 开放平台 WebSocket 网关（AppID + AppSecret）。

与 OneBot 系适配器一致，这里把官方事件翻译成 OneBot 事件后推入
``MessageQueue``，下游 Pipeline / EventBus / 命令 / 插件无需区分平台。
"""

from __future__ import annotations

import asyncio
import json
from logging import Logger
from typing import Any

from atribot.core.atri_config import PlatformInstanceConfig, QQBotPlatformConfig
from atribot.core.logger import get_named_logger
from atribot.core.platform import register_adapter
from atribot.core.platform.base import PlatformAdapter
from atribot.core.platform.message_queue import MessageQueue
from atribot.core.platform.qqbot.api import QQBotApiClient, QQBotAPIError
from atribot.core.platform.qqbot.auth import QQBotTokenManager
from atribot.core.platform.qqbot.gateway import QQBotGatewayClient
from atribot.core.platform.qqbot.id_map import QQBotIdMapper, make_synthetic_id
from atribot.core.platform.qqbot.message_event import QQBotMessageEvent
from atribot.core.platform.qqbot.send import QQBotSendClient
from atribot.core.platform.qqbot.translate import build_event, safe_int
from atribot.core.platform.send_client import LoginInfo
from atribot.core.type.chat_message_types import SendMessage
from atribot.core.type.onebot_event_types import PostType

DEFAULT_INTENTS = 1 << 25
"""默认订阅：公域群聊 @ 消息 + C2C 消息 + 机器人入群/退群等事件"""

SEEN_MESSAGE_LIMIT = 512
"""重复消息去重缓存容量（@ 事件与全量群消息事件可能重复推送同一条消息）"""


@register_adapter("qqbot")
class QQBotAdapter(PlatformAdapter):
    """QQ 官方机器人适配器（WebSocket 网关）"""

    _log_name: str = "QQBotAdapter"
    _message_event_cls = QQBotMessageEvent
    _send_client_cls = QQBotSendClient
    _default_intents: int = DEFAULT_INTENTS

    def __init__(self, config: PlatformInstanceConfig, queue: MessageQueue) -> None:
        if not isinstance(config, QQBotPlatformConfig):
            raise ValueError(
                f"qqbot 适配器需要 connection_type='qqbot' 的平台配置，收到: {config.connection_type}"
            )

        self._config = config
        self._queue = queue
        self._source_name = config.source_name or "qqbot"
        self._log: Logger = get_named_logger(f"{self._log_name}.{self._source_name}")
        self._started = False
        self._conn_task: asyncio.Task[None] | None = None
        self._self_id: int = 0
        self._self_openids: set[str] = set()
        self._seen_message_ids: dict[str, bool] = {}

        self._id_mapper = QQBotIdMapper(config.id_map, log=self._log)
        self._tokens = QQBotTokenManager(
            config.app_id,
            config.app_secret,
            log=self._log.getChild("Token"),
        )
        self._api = QQBotApiClient(
            self._tokens,
            sandbox=config.sandbox,
            log=self._log.getChild("API"),
        )
        self._gateway = QQBotGatewayClient(
            self._api,
            self._tokens,
            intents=int(config.intents or self._default_intents),
            log=self._log.getChild("Gateway"),
        )
        self._send_client: QQBotSendClient = self._send_client_cls(
            self._api,
            self._id_mapper,
            log=self._log.getChild("Send"),
            text_chunk_size=config.text_chunk_size,
            max_passive_replies=config.max_passive_replies,
            allow_proactive=config.allow_proactive,
        )


    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_connected(self) -> bool:
        return self._gateway.is_connected

    def get_connection_info(self) -> dict[str, Any]:
        return {
            "adapter": type(self).__name__,
            "is_started": self._started,
            "is_running": self._gateway.is_running,
            "is_connected": self.is_connected,
            "retry_count": self._gateway.retry_count,
            "sandbox": self._config.sandbox,
            "intents": self._gateway.intents,
            "bot_id": self._self_id,
        }

    async def start(self) -> None:
        """启动网关连接"""
        if self._started:
            return

        self._gateway.add_listener(self._on_dispatch)
        self._log.info(
            "正在连接 QQ 官方机器人 (app_id=%s, sandbox=%s, intents=%s)",
            self._config.app_id,
            self._config.sandbox,
            self._gateway.intents,
        )

        self._conn_task = asyncio.create_task(
            self._gateway.start(),
            name=f"QQBotGateway.{self._source_name}",
        )
        self._started = True

        if await self._gateway.wait_for_connection(timeout=10.0):
            self._log.info("QQ 官方机器人连接已建立")
        else:
            self._log.warning("QQ 官方机器人连接尚未建立（仍在后台重试）")

    async def stop(self) -> None:
        """停止网关连接并释放资源"""
        if not self._started:
            return

        self._log.info("正在停止 QQ 官方机器人适配器...")
        try:
            self._gateway.remove_listener(self._on_dispatch)
        except Exception:
            self._log.warning("移除网关监听器时出现异常", exc_info=True)

        await self._gateway.close()

        if self._conn_task is not None and not self._conn_task.done():
            self._conn_task.cancel()
            try:
                await self._conn_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self._log.debug("网关任务退出时出现异常", exc_info=True)
        self._conn_task = None

        await self._send_client.close()
        await self._api.close()
        await self._tokens.close()

        self._started = False
        self._log.info("QQ 官方机器人适配器已停止")

    async def send(self, message: SendMessage) -> Any:
        return await self._send_client.send(message)

    def get_client(self) -> object:
        return self._send_client

    async def call_api(self, action: str, params: dict) -> Any:
        """通用动作调用（仅支持发送 / 撤回 / 账号查询）"""
        if action == "get_me":
            try:
                return await self._api.get_me()
            except QQBotAPIError as exc:
                self._log.warning("调用 /users/@me 失败: %s", exc)
                return None
        return await self._send_client.async_send(action, params)

    async def get_login_info(self) -> LoginInfo | None:
        """获取机器人自身账号信息"""
        info = await self._send_client.get_login_info()
        if info:
            self._update_self_id({"id": info["user_id"], "username": info["nickname"]})
        return info

    async def _on_dispatch(self, payload: dict) -> None:
        """网关 dispatch 回调：翻译为 OneBot 事件并入队"""
        event_type = payload.get("t")
        if event_type == "READY":
            self._update_self_id(self._gateway.bot_user)
            return

        try:
            event = build_event(
                payload,
                id_mapper=self._id_mapper,
                self_id=self._self_id,
                self_openids=self._self_openids,
            )
        except Exception:
            self._log.exception(
                "QQ 官方事件翻译失败: %s",
                json.dumps(payload, ensure_ascii=False)[:300],
            )
            return

        if event is None:
            self._log.debug("忽略未处理的 QQ 官方事件: %s", event_type)
            return

        meta = event.primeval.get("_qqbot") if isinstance(event.primeval, dict) else None
        if isinstance(meta, dict) and event.post_type == PostType.MESSAGE:
            if self._is_duplicate_message(meta, is_at=bool(getattr(event, "is_at", False))):
                self._log.debug(
                    "忽略重复的 QQ 官方消息: %s (%s)",
                    event_type,
                    meta.get("raw_message_id"),
                )
                return
            self._remember_inbound(event, meta)

        msg = self._message_event_cls(
            event=event,
            source=self._source_name,
            direction="incoming",
            send_client=self._send_client,
        )
        pushed = await self._queue.push(msg)
        if not pushed:
            self._log.warning(
                "QQ 官方消息未能入队（队列满）: type=%s event=%s",
                type(event).__name__,
                event_type,
            )

    def _is_duplicate_message(self, meta: dict, *, is_at: bool) -> bool:
        """按官方消息 ID 去重

        ``GROUP_AT_MESSAGE_CREATE`` 与 ``GROUP_MESSAGE_CREATE`` 可能推送同一条消息。
        若先到的全量群消息未被识别为 @，后到的 @ 事件仍会放行，避免漏掉对机器人的 @。
        """
        raw_id = str(meta.get("raw_message_id") or "")
        if not raw_id:
            return False

        seen_at = self._seen_message_ids.get(raw_id)
        if seen_at is not None:
            if is_at and not seen_at:
                self._seen_message_ids[raw_id] = True
                return False
            return True

        self._seen_message_ids[raw_id] = is_at
        while len(self._seen_message_ids) > SEEN_MESSAGE_LIMIT:
            self._seen_message_ids.pop(next(iter(self._seen_message_ids)))
        return False

    def _remember_inbound(self, event: Any, meta: dict) -> None:
        """登记入站消息，供被动回复使用"""
        group_id = getattr(event, "group_id", None)
        if group_id:
            kind = "group"
            target_id = int(group_id)
            openid = str(meta.get("group_openid") or "")
        else:
            kind = "private"
            target_id = int(getattr(event, "user_id", 0) or 0)
            openid = str(meta.get("user_openid") or "")

        self._send_client.remember_inbound(
            kind=kind,
            target_id=target_id,
            raw_message_id=str(meta.get("raw_message_id") or ""),
            event_id=str(meta.get("event_id") or "") or None,
            openid=openid,
        )

    def _update_self_id(self, user: dict) -> None:
        for key in ("id", "openid", "union_openid"):
            raw = user.get(key)
            if isinstance(raw, str) and raw.strip():
                self._self_openids.add(raw.strip())
        raw_id = user.get("id")
        if raw_id is None:
            return
        value = safe_int(raw_id, 0)
        if value == 0:
            value = make_synthetic_id("user", str(raw_id))
            self._log.warning(
                "机器人 id 非数字（%r），已使用合成 ID %s", raw_id, value
            )
        self._self_id = value
