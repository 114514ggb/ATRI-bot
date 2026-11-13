"""QQ 官方机器人适配器离线单测

覆盖：配置解析、适配器注册、openid 映射、事件翻译、CQ 解析、
发送 payload（被动回复 / 主动消息 / 文本分片 / 富媒体上传）。

运行：uv run python -m pytest tests/test_qqbot_adapter.py -q
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

from atribot.core.atri_config import PlatformsConfig, QQBotPlatformConfig
from atribot.core.platform import get_adapter_class, get_registered_adapters
from atribot.core.platform.qqbot.cq import parse_cq_string
from atribot.core.platform.qqbot.id_map import QQBotIdMapper, make_synthetic_id
from atribot.core.platform.qqbot.send import QQBotSendClient
from atribot.core.platform.qqbot.translate import build_event
from atribot.core.type.onebot_event_types import (
    GroupIncreaseEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
)

SELF_ID = 10001
GROUP_OPENID = "group-openid-AAA"
USER_OPENID = "user-openid-BBB"


class FakeApi:
    """记录调用参数的假 API"""

    def __init__(self) -> None:
        self.group_messages: list[tuple[str, dict[str, Any]]] = []
        self.c2c_messages: list[tuple[str, dict[str, Any]]] = []
        self.uploads: list[dict[str, Any]] = []
        self.deleted: list[tuple[str, str]] = []
        self.downloads: list[str] = []

    async def send_group_message(self, group_openid: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.group_messages.append((group_openid, payload))
        return {"id": f"raw-{len(self.group_messages)}", "timestamp": "1"}

    async def send_c2c_message(self, openid: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.c2c_messages.append((openid, payload))
        return {"id": f"raw-c2c-{len(self.c2c_messages)}", "timestamp": "1"}

    async def upload_group_media(
        self,
        group_openid: str,
        file_type: int,
        *,
        url: str | None = None,
        file_data: str | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        self.uploads.append(
            {
                "target": group_openid,
                "file_type": file_type,
                "url": url,
                "file_data": file_data,
                "file_name": file_name,
            }
        )
        return {"file_info": f"file-info-{len(self.uploads)}"}

    async def upload_c2c_media(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return await self.upload_group_media(*args, **kwargs)

    async def delete_group_message(self, group_openid: str, message_id: str) -> dict[str, Any]:
        self.deleted.append((group_openid, message_id))
        return {}

    async def download(self, url: str, *, max_bytes: int = 20 * 1024 * 1024) -> bytes | None:
        self.downloads.append(url)
        return b"remote-bytes"

    async def get_me(self) -> dict[str, Any]:
        return {"id": "12345", "username": "ATRI"}


def make_send_client(**kwargs: Any) -> tuple[QQBotSendClient, FakeApi, QQBotIdMapper]:
    api = FakeApi()
    mapper = QQBotIdMapper()
    client = QQBotSendClient(api, mapper, **kwargs)  # type: ignore[arg-type]
    return client, api, mapper


def group_payload(content: str = " 你好呀", attachments: list[dict] | None = None) -> dict[str, Any]:
    return {
        "id": "event-id-1",
        "op": 0,
        "t": "GROUP_AT_MESSAGE_CREATE",
        "s": 1,
        "d": {
            "id": "raw-msg-1",
            "content": content,
            "group_openid": GROUP_OPENID,
            "author": {"member_openid": USER_OPENID},
            "timestamp": "2026-01-02T03:04:05+08:00",
            "attachments": attachments or [],
        },
    }


class TestPlatformConfig:
    """配置解析"""

    def test_parses_qqbot_entry(self) -> None:
        config = PlatformsConfig.from_dict(
            {
                "official": {
                    "adapter": "qqbot",
                    "connection_type": "qqbot",
                    "app_id": "1024",
                    "app_secret": "secret",
                    "sandbox": True,
                    "text_chunk_size": 800,
                    "max_passive_replies": 3,
                    "allow_proactive": True,
                    "id_map": {"group": {GROUP_OPENID: 123456}},
                }
            }
        )
        instance = config.instances["official"]
        assert isinstance(instance, QQBotPlatformConfig)
        assert instance.app_id == "1024"
        assert instance.sandbox is True
        assert instance.text_chunk_size == 800
        assert instance.max_passive_replies == 3
        assert instance.allow_proactive is True
        assert instance.source_name == "official"
        assert instance.id_map == {"group": {GROUP_OPENID: 123456}}

    def test_adapter_is_registered(self) -> None:
        assert "qqbot" in get_registered_adapters()
        assert get_adapter_class("qqbot") is not None


class TestIdMapping:
    """openid → 整数映射"""

    def test_is_stable_and_in_reserved_range(self) -> None:
        first = make_synthetic_id("group", GROUP_OPENID)
        second = make_synthetic_id("group", GROUP_OPENID)
        assert first == second
        assert first > (1 << 62)
        assert first < (1 << 63)

    def test_kinds_do_not_collide(self) -> None:
        assert make_synthetic_id("group", "same") != make_synthetic_id("user", "same")

    def test_override_and_reverse(self) -> None:
        mapper = QQBotIdMapper({"group": {GROUP_OPENID: 42}})
        assert mapper.to_id("group", GROUP_OPENID) == 42
        assert mapper.to_raw("group", 42) == GROUP_OPENID

    def test_empty_openid_maps_to_zero(self) -> None:
        mapper = QQBotIdMapper()
        assert mapper.to_id("group", "") == 0
        assert mapper.to_raw("group", 0) is None


class TestTranslate:
    """官方事件 → OneBot 事件"""

    def test_group_at_message(self) -> None:
        mapper = QQBotIdMapper()
        event = build_event(group_payload(), id_mapper=mapper, self_id=SELF_ID)

        assert isinstance(event, GroupMessageEvent)
        assert event.group_id == mapper.to_id("group", GROUP_OPENID)
        assert event.user_id == mapper.to_id("user", USER_OPENID)
        assert event.is_at is True
        assert event.pure_text == "你好呀"
        assert event.sender["nickname"]
        assert event.primeval["_qqbot"]["group_openid"] == GROUP_OPENID
        assert event.primeval["_qqbot"]["raw_message_id"] == "raw-msg-1"

    def test_group_plain_message_is_not_at(self) -> None:
        mapper = QQBotIdMapper()
        payload = group_payload(content="普通聊天")
        payload["t"] = "GROUP_MESSAGE_CREATE"
        event = build_event(payload, id_mapper=mapper, self_id=SELF_ID)

        assert isinstance(event, GroupMessageEvent)
        assert event.group_id == mapper.to_id("group", GROUP_OPENID)
        assert event.is_at is False
        assert event.pure_text == "普通聊天"

    def test_group_message_mention_tag_marks_at(self) -> None:
        bot_openid = "bot-openid-ZZZ"
        self_id = make_synthetic_id("user", bot_openid)
        payload = group_payload(content=f"<@!{bot_openid}> 在吗")
        payload["t"] = "GROUP_MESSAGE_CREATE"
        event = build_event(payload, id_mapper=QQBotIdMapper(), self_id=self_id)

        assert isinstance(event, GroupMessageEvent)
        assert event.is_at is True
        assert event.pure_text == "在吗"
        assert [s.type for s in event.segments] == ["at", "text"]

    def test_group_message_mentions_is_you_marks_at(self) -> None:
        payload = group_payload(content="在吗")
        payload["t"] = "GROUP_MESSAGE_CREATE"
        payload["d"]["mentions"] = [
            {"member_openid": "other-openid", "is_you": True}
        ]
        event = build_event(payload, id_mapper=QQBotIdMapper(), self_id=SELF_ID)

        assert isinstance(event, GroupMessageEvent)
        assert event.is_at is True

    def test_group_message_other_mention_is_not_at(self) -> None:
        mapper = QQBotIdMapper()
        payload = group_payload(content="<@other-openid> 你好")
        payload["t"] = "GROUP_MESSAGE_CREATE"
        event = build_event(payload, id_mapper=mapper, self_id=SELF_ID)

        assert isinstance(event, GroupMessageEvent)
        assert event.is_at is False
        assert event.pure_text == "你好"
        assert event.segments[0].type == "at"  # type: ignore[attr-defined]

    def test_bot_authored_group_message_is_ignored(self) -> None:
        payload = group_payload(content="别的机器人说的话")
        payload["t"] = "GROUP_MESSAGE_CREATE"
        payload["d"]["author"]["bot"] = True

        assert build_event(payload, id_mapper=QQBotIdMapper(), self_id=SELF_ID) is None

    def test_group_image_attachment_becomes_image_segment(self) -> None:
        mapper = QQBotIdMapper()
        payload = group_payload(
            content="看图",
            attachments=[
                {
                    "content_type": "image/png",
                    "filename": "a.png",
                    "size": 123,
                    "url": "https://example.com/a.png",
                }
            ],
        )
        event = build_event(payload, id_mapper=mapper, self_id=SELF_ID)

        assert isinstance(event, GroupMessageEvent)
        assert [s.type for s in event.segments] == ["text", "image"]
        image = event.segments[1]
        assert image.url == "https://example.com/a.png"  # type: ignore[attr-defined]

    def test_c2c_message(self) -> None:
        mapper = QQBotIdMapper()
        payload = {
            "id": "event-id-2",
            "t": "C2C_MESSAGE_CREATE",
            "d": {
                "id": "raw-msg-2",
                "content": "私聊",
                "author": {"user_openid": USER_OPENID},
                "timestamp": "1767225845",
            },
        }
        event = build_event(payload, id_mapper=mapper, self_id=SELF_ID)

        assert isinstance(event, PrivateMessageEvent)
        assert event.user_id == mapper.to_id("user", USER_OPENID)
        assert getattr(event, "group_id", None) is None

    def test_group_add_robot_notice(self) -> None:
        mapper = QQBotIdMapper()
        payload = {
            "id": "event-id-3",
            "t": "GROUP_ADD_ROBOT",
            "d": {
                "group_openid": GROUP_OPENID,
                "op_member_openid": USER_OPENID,
                "timestamp": "1767225845",
            },
        }
        event = build_event(payload, id_mapper=mapper, self_id=SELF_ID)

        assert isinstance(event, GroupIncreaseEvent)
        assert event.group_id == mapper.to_id("group", GROUP_OPENID)
        assert event.user_id == SELF_ID

    def test_unknown_event_returns_none(self) -> None:
        mapper = QQBotIdMapper()
        payload = {"t": "MESSAGE_REACTION_ADD", "d": {}}
        assert build_event(payload, id_mapper=mapper, self_id=SELF_ID) is None


class TestWebPanelConfig:
    """面板配置校验与密钥打码"""

    def test_qqbot_connection_type_is_valid(self) -> None:
        from atribot.web_panel.routes.config import _validate_main_config

        _validate_main_config(
            {
                "platforms": {
                    "qq": {
                        "adapter": "qqbot",
                        "connection_type": "qqbot",
                        "app_id": "1024",
                        "app_secret": "secret",
                    }
                },
                "root_user_id": 1,
                "database": {"host": "h", "port": 5432, "user": "u", "password": "p"},
            }
        )

    def test_qqbot_requires_credentials(self) -> None:
        from fastapi import HTTPException

        from atribot.web_panel.routes.config import _validate_main_config

        with pytest.raises(HTTPException) as excinfo:
            _validate_main_config(
                {
                    "platforms": {
                        "qq": {"adapter": "qqbot", "connection_type": "qqbot"}
                    },
                    "root_user_id": 1,
                    "database": {"host": "h", "port": 5432, "user": "u", "password": "p"},
                }
            )
        detail = str(excinfo.value.detail)
        assert "app_id" in detail and "app_secret" in detail

    def test_app_secret_is_masked_and_restored(self) -> None:
        from atribot.web_panel.routes.config import (
            _KEEP_SENTINEL,
            mask_secrets,
            restore_secrets,
        )

        masked = mask_secrets(
            "main",
            {
                "platforms": {
                    "qq": {
                        "connection_type": "qqbot",
                        "app_id": "1024",
                        "app_secret": "real-secret",
                    }
                }
            },
        )
        platform = masked["platforms"]["qq"]
        assert platform["app_secret"] == _KEEP_SENTINEL
        assert platform["app_id"] == "1024"

        new = {
            "platforms": {
                "qq": {
                    "connection_type": "qqbot",
                    "app_id": "1024",
                    "app_secret": _KEEP_SENTINEL,
                }
            }
        }
        restore_secrets(
            "main",
            new,
            {"platforms": {"qq": {"app_secret": "real-secret"}}},
        )
        assert new["platforms"]["qq"]["app_secret"] == "real-secret"


class FakeQueue:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def push(self, msg: Any) -> bool:
        self.items.append(msg)
        return True


class TestAdapter:
    """适配器装配与事件入队"""

    @pytest.mark.asyncio
    async def test_dispatch_translates_and_enqueues(self) -> None:
        from atribot.core.platform.qqbot.adapter import QQBotAdapter

        queue = FakeQueue()
        adapter = QQBotAdapter(
            QQBotPlatformConfig(
                adapter="qqbot",
                app_id="1024",
                app_secret="secret",
                source_name="official",
            ),
            queue,  # type: ignore[arg-type]
        )
        adapter._self_id = SELF_ID

        await adapter._on_dispatch(group_payload())

        assert len(queue.items) == 1
        envelope = queue.items[0]
        assert envelope.source == "official"
        assert envelope.group_id == adapter._id_mapper.to_id("group", GROUP_OPENID)
        assert envelope.is_at is True
        assert envelope.get_platform_openid("group") == GROUP_OPENID
        assert envelope.get_platform_openid("user") == USER_OPENID

        assert isinstance(adapter.get_client(), QQBotSendClient)

        info = adapter.get_connection_info()
        assert info["adapter"] == "QQBotAdapter"
        assert info["is_connected"] is False

    @pytest.mark.asyncio
    async def test_dispatch_group_all_message_enqueues_without_at(self) -> None:
        from atribot.core.platform.qqbot.adapter import QQBotAdapter

        queue = FakeQueue()
        adapter = QQBotAdapter(
            QQBotPlatformConfig(
                adapter="qqbot",
                app_id="1024",
                app_secret="secret",
                source_name="official",
            ),
            queue,  # type: ignore[arg-type]
        )
        adapter._self_id = SELF_ID

        payload = group_payload(content="群里随便聊聊")
        payload["t"] = "GROUP_MESSAGE_CREATE"
        await adapter._on_dispatch(payload)

        assert len(queue.items) == 1
        envelope = queue.items[0]
        assert envelope.group_id == adapter._id_mapper.to_id("group", GROUP_OPENID)
        assert envelope.is_at is False

    @pytest.mark.asyncio
    async def test_dispatch_deduplicates_same_raw_message_id(self) -> None:
        from atribot.core.platform.qqbot.adapter import QQBotAdapter

        queue = FakeQueue()
        adapter = QQBotAdapter(
            QQBotPlatformConfig(
                adapter="qqbot",
                app_id="1024",
                app_secret="secret",
                source_name="official",
            ),
            queue,  # type: ignore[arg-type]
        )
        adapter._self_id = SELF_ID

        at_payload = group_payload()
        all_payload = group_payload()
        all_payload["t"] = "GROUP_MESSAGE_CREATE"

        await adapter._on_dispatch(at_payload)
        await adapter._on_dispatch(all_payload)

        assert len(queue.items) == 1
        assert queue.items[0].is_at is True

    @pytest.mark.asyncio
    async def test_dispatch_keeps_at_event_after_plain_duplicate(self) -> None:
        from atribot.core.platform.qqbot.adapter import QQBotAdapter

        queue = FakeQueue()
        adapter = QQBotAdapter(
            QQBotPlatformConfig(
                adapter="qqbot",
                app_id="1024",
                app_secret="secret",
                source_name="official",
            ),
            queue,  # type: ignore[arg-type]
        )
        adapter._self_id = SELF_ID

        all_payload = group_payload(content="在吗")
        all_payload["t"] = "GROUP_MESSAGE_CREATE"
        at_payload = group_payload(content=" 在吗")

        await adapter._on_dispatch(all_payload)
        await adapter._on_dispatch(at_payload)
        await adapter._on_dispatch(all_payload)

        assert len(queue.items) == 2
        assert [item.is_at for item in queue.items] == [False, True]


class TestGateway:
    """网关协议（使用本地假 WebSocket 服务端）"""

    @pytest.mark.asyncio
    async def test_identify_ready_and_dispatch(self) -> None:
        import asyncio
        import json

        from aiohttp import web

        from atribot.core.platform.qqbot.gateway import QQBotGatewayClient

        gateway_received: list[dict] = []
        dispatched: list[dict] = []
        ready = asyncio.Event()

        async def ws_handler(request: web.Request) -> web.WebSocketResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"op": 10, "d": {"heartbeat_interval": 1000}})
            try:
                async for message in ws:
                    if message.type != web.WSMsgType.TEXT:
                        break
                    payload = json.loads(message.data)
                    gateway_received.append(payload)
                    if payload.get("op") == 2:
                        await ws.send_json(
                            {
                                "op": 0,
                                "t": "READY",
                                "s": 1,
                                "id": "ready",
                                "d": {
                                    "session_id": "session-1",
                                    "user": {"id": "12345", "username": "ATRI"},
                                },
                            }
                        )
                        await ws.send_json(group_payload())
            except (ConnectionResetError, RuntimeError):
                pass
            return ws

        app = web.Application()
        app.router.add_get("/ws", ws_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        try:
            sockets = site._server.sockets  # type: ignore[union-attr]
            port = sockets[0].getsockname()[1]
            ws_url = f"http://127.0.0.1:{port}/ws"

            class StubApi:
                async def get_gateway_url(self) -> str:
                    return ws_url

            class StubTokens:
                async def get_token(self) -> str:
                    return "fake-token"

            gateway = QQBotGatewayClient(
                StubApi(),  # type: ignore[arg-type]
                StubTokens(),  # type: ignore[arg-type]
                intents=1 << 25,
            )

            async def on_dispatch(payload: dict) -> None:
                dispatched.append(payload)
                if payload.get("t") == "GROUP_AT_MESSAGE_CREATE":
                    ready.set()

            gateway.add_listener(on_dispatch)
            task = asyncio.create_task(gateway.start())
            try:
                await asyncio.wait_for(ready.wait(), timeout=10.0)
                assert gateway.is_connected is True
                assert gateway.session_id == "session-1"
                assert gateway.bot_user["username"] == "ATRI"

                identify = next(p for p in gateway_received if p.get("op") == 2)
                assert identify["d"]["token"] == "QQBot fake-token"
                assert identify["d"]["intents"] == 1 << 25
                assert identify["d"]["shard"] == [0, 1]

                group_events = [
                    p for p in dispatched if p.get("t") == "GROUP_AT_MESSAGE_CREATE"
                ]
                assert group_events
                event = build_event(
                    group_events[0], id_mapper=QQBotIdMapper(), self_id=12345
                )
                assert isinstance(event, GroupMessageEvent)
            finally:
                await gateway.close()
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        finally:
            await runner.cleanup()


class TestCqParsing:
    """CQ 码解析"""

    def test_reply_text_image_and_escapes(self) -> None:
        segments = parse_cq_string(
            "[CQ:reply,id=42]你好&#44;世界[CQ:image,file=file:///tmp/a.png]&amp;"
        )

        assert segments[0] == {"type": "reply", "data": {"id": "42"}}
        assert segments[1] == {"type": "text", "data": {"text": "你好,世界"}}
        assert segments[2] == {"type": "image", "data": {"file": "file:///tmp/a.png"}}
        assert segments[3] == {"type": "text", "data": {"text": "&"}}

    def test_empty_string(self) -> None:
        assert parse_cq_string("") == []


class TestSendClient:
    """发送客户端"""

    @pytest.mark.asyncio
    async def test_uses_passive_reply_and_increments_seq(self) -> None:
        client, api, mapper = make_send_client()
        group_id = mapper.to_id("group", GROUP_OPENID)
        mapper.to_id("user", USER_OPENID)
        client.remember_inbound(
            kind="group",
            target_id=group_id,
            raw_message_id="raw-msg-1",
            event_id="event-id-1",
            openid=GROUP_OPENID,
        )

        await client.send_group_msg(group_id, "第一条")
        await client.send_group_msg(group_id, "第二条")

        assert len(api.group_messages) == 2
        first = api.group_messages[0][1]
        second = api.group_messages[1][1]
        assert first["msg_id"] == "raw-msg-1"
        assert first["msg_seq"] == 1
        assert first["msg_type"] == 0
        assert first["content"] == "第一条"
        assert second["msg_seq"] == 2

    @pytest.mark.asyncio
    async def test_drops_when_no_passive_target(self) -> None:
        client, api, mapper = make_send_client()
        group_id = mapper.to_id("group", GROUP_OPENID)

        result = await client.send_group_msg(group_id, "主动消息")

        assert result is None
        assert api.group_messages == []

    @pytest.mark.asyncio
    async def test_allows_proactive_when_enabled(self) -> None:
        client, api, mapper = make_send_client(allow_proactive=True)
        group_id = mapper.to_id("group", GROUP_OPENID)

        result = await client.send_group_msg(group_id, "主动消息")

        assert result is not None
        payload = api.group_messages[0][1]
        assert "msg_id" not in payload
        assert payload["content"] == "主动消息"

    @pytest.mark.asyncio
    async def test_stops_after_max_passive_replies(self) -> None:
        client, api, mapper = make_send_client(max_passive_replies=2)
        group_id = mapper.to_id("group", GROUP_OPENID)
        client.remember_inbound(
            kind="group",
            target_id=group_id,
            raw_message_id="raw-msg-1",
            event_id=None,
            openid=GROUP_OPENID,
        )

        await client.send_group_msg(group_id, "1")
        await client.send_group_msg(group_id, "2")
        result = await client.send_group_msg(group_id, "3")

        assert result is None
        assert len(api.group_messages) == 2

    @pytest.mark.asyncio
    async def test_chunks_long_text(self) -> None:
        client, api, mapper = make_send_client(text_chunk_size=200)
        group_id = mapper.to_id("group", GROUP_OPENID)
        client.remember_inbound(
            kind="group",
            target_id=group_id,
            raw_message_id="raw-msg-1",
            event_id=None,
            openid=GROUP_OPENID,
        )

        text = "\n".join("x" * 50 for _ in range(10))
        await client.send_group_msg(group_id, text)

        assert len(api.group_messages) > 1
        for _, payload in api.group_messages:
            assert len(payload["content"]) <= 200

    @pytest.mark.asyncio
    async def test_uploads_local_image_as_base64(self, tmp_path) -> None:
        client, api, mapper = make_send_client()
        group_id = mapper.to_id("group", GROUP_OPENID)
        client.remember_inbound(
            kind="group",
            target_id=group_id,
            raw_message_id="raw-msg-1",
            event_id=None,
            openid=GROUP_OPENID,
        )

        image_path = tmp_path / "pic.png"
        image_path.write_bytes(b"png-bytes")

        result = await client.send_group_pictures(group_id, str(image_path))

        assert result is not None
        upload = api.uploads[0]
        assert upload["file_type"] == 1
        assert base64.b64decode(upload["file_data"]) == b"png-bytes"
        assert upload["url"] is None
        media_payload = api.group_messages[-1][1]
        assert media_payload["msg_type"] == 7
        assert media_payload["media"] == {"file_info": "file-info-1"}

    @pytest.mark.asyncio
    async def test_uploads_remote_image_by_url(self) -> None:
        client, api, mapper = make_send_client()
        group_id = mapper.to_id("group", GROUP_OPENID)
        client.remember_inbound(
            kind="group",
            target_id=group_id,
            raw_message_id="raw-msg-1",
            event_id=None,
            openid=GROUP_OPENID,
        )

        await client.send_group_pictures(group_id, "https://example.com/a.png")

        upload = api.uploads[0]
        assert upload["url"] == "https://example.com/a.png"
        assert upload["file_data"] is None
        assert api.downloads == []

    @pytest.mark.asyncio
    async def test_cq_string_is_parsed_into_text_and_media(self, tmp_path) -> None:
        client, api, mapper = make_send_client()
        group_id = mapper.to_id("group", GROUP_OPENID)
        client.remember_inbound(
            kind="group",
            target_id=group_id,
            raw_message_id="raw-msg-1",
            event_id=None,
            openid=GROUP_OPENID,
        )
        image_path = tmp_path / "emoji.png"
        image_path.write_bytes(b"emoji")

        await client.send_group_msg(
            group_id, f"文字[CQ:image,file=file://{image_path.as_posix()}]"
        )

        assert api.group_messages[0][1]["content"] == "文字"
        assert api.uploads[0]["file_type"] == 1

    @pytest.mark.asyncio
    async def test_capability_noops(self) -> None:
        client, _api, _mapper = make_send_client()

        assert await client.set_msg_emoji_like(1, 66) is None
        assert await client.set_input_status(1, 1) is None
        assert await client.set_group_ban(1, 2) is None
        assert await client.get_group_info(1) is None
        assert await client.get_msg_details(1) is None

    @pytest.mark.asyncio
    async def test_get_login_info(self) -> None:
        client, _api, _mapper = make_send_client()

        info = await client.get_login_info()

        assert info == {"user_id": 12345, "nickname": "ATRI"}

    @pytest.mark.asyncio
    async def test_async_send_routes_group_message(self) -> None:
        client, api, mapper = make_send_client(allow_proactive=True)
        group_id = mapper.to_id("group", GROUP_OPENID)

        await client.async_send(
            "send_group_msg", {"group_id": group_id, "message": "hi"}
        )

        assert api.group_messages[0][1]["content"] == "hi"
