"""WebUI 聊天（chat_engine 会话引擎）的单元测试

覆盖：附件分类与限额、合成消息事件、上下文序列化往返（媒体降级为注记）、
用户消息构建（直传/降级）、会话 id 分配与删除复用、展示时间线重建、
WebuiSendClient 文件投递与 file_resolver 注入。
"""

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.web_panel.routes import chat_engine as engine


@pytest.fixture(autouse=True)
def _fake_memory_system():
    """AgentContext 的默认压缩策略在构造时会向容器要 MemorySystem，
    测试环境注册一个跳过重依赖构造的替身，结束时注销"""
    from atribot.LLMchat.memory.memory_system import MemorySystem

    class _FakeMemory(MemorySystem):
        def __init__(self):
            pass

    fake = _FakeMemory()
    container.register("_test_fake_memory", fake)
    yield
    container.unregister("_test_fake_memory")


# ---------- 附件分类与限额 ----------

def test_classify_file_by_extension_and_mime():
    assert engine.classify_file("a.PNG") == "image"
    assert engine.classify_file("b.Mp3") == "audio"
    assert engine.classify_file("c.mp4") == "video"
    assert engine.classify_file("d.pdf", "application/pdf") == "file"
    assert engine.classify_file("noext", "audio/ogg") == "audio"
    assert engine.classify_file("noext2", "image/png") == "image"


def test_size_limits():
    assert engine.size_limit_for("image") == 30 * 1024 * 1024
    assert engine.size_limit_for("audio") == 50 * 1024 * 1024
    assert engine.size_limit_for("video") == 200 * 1024 * 1024
    assert engine.size_limit_for("file") == 100 * 1024 * 1024


def test_save_and_get_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    info = engine.save_attachment("photo.JPG", "image/jpeg", b"\xff\xd8\xff")
    assert info["kind"] == "image"
    assert info["size"] == 3
    assert engine.get_attachment(info["id"])["name"] == "photo.JPG"
    assert engine.get_attachment("nonexistent") is None


# ---------- 合成消息事件 ----------

def test_webui_message_event_is_private_chat():
    event = engine.WebuiMessageEvent(7)
    assert isinstance(event, atriMessageEvent)
    assert event.user_id == 7
    assert event.chat_scope == "private"
    assert event.group_id is None
    assert event.source == "webui"


@pytest.mark.asyncio
async def test_webui_message_event_send_fails_without_platform():
    event = engine.WebuiMessageEvent(7)
    with pytest.raises(RuntimeError):
        await event.send(object())


# ---------- WebUI 文件投递（WebuiSendClient） ----------

def _register_session(session_id: int) -> "engine.ChatSession":
    session = engine.ChatSession(session_id)
    engine.registry.sessions[session_id] = session
    return session


@pytest.mark.asyncio
async def test_webui_deliver_file_registers_attachment_and_broadcasts(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    session = _register_session(3)
    queue = session.subscribe()
    event = engine.WebuiMessageEvent(3)
    try:
        result = await event.deliver_file(
            "base64://" + base64.b64encode(b"hello").decode(),
            name="note.txt",
            local_Path_type=False,
        )
        assert result["name"] == "note.txt"
        info = engine.get_attachment(result["file_id"])
        assert info["size"] == 5

        msg = queue.get_nowait()
        assert msg["type"] == "attachment"
        assert msg["file"]["name"] == "note.txt"
        assert msg["file"]["url"].startswith("/admin/api/chat/files/")
        assert session.pending_files == [msg["file"]]
    finally:
        engine.registry.sessions.pop(3, None)
        engine._attachments.clear()


@pytest.mark.asyncio
async def test_webui_deliver_image_sniffs_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    _register_session(4)
    event = engine.WebuiMessageEvent(4)
    raw = tmp_path / "rawfile"
    raw.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    try:
        result = await event.deliver_image(str(raw), local_Path_type=True)
        assert result["name"].endswith(".png")
        assert engine.get_attachment(result["file_id"])["kind"] == "image"
    finally:
        engine.registry.sessions.pop(4, None)
        engine._attachments.clear()


@pytest.mark.asyncio
async def test_webui_deliver_merge_text_broadcasts(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    session = _register_session(5)
    queue = session.subscribe()
    event = engine.WebuiMessageEvent(5)
    try:
        await event.deliver_merge_text("print(1)", source="执行的代码")
        msg = queue.get_nowait()
        assert msg["type"] == "merge_text"
        assert msg["source"] == "执行的代码"
        assert msg["message"] == "print(1)"
    finally:
        engine.registry.sessions.pop(5, None)


@pytest.mark.asyncio
async def test_webui_send_client_raises_when_session_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    event = engine.WebuiMessageEvent(999)  # 未注册的会话 id
    with pytest.raises(RuntimeError):
        await event.deliver_file(
            "base64://" + base64.b64encode(b"x").decode(),
            name="a.txt",
            local_Path_type=False,
        )


@pytest.mark.asyncio
async def test_webui_send_client_rejects_oversized_image(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    _register_session(6)
    event = engine.WebuiMessageEvent(6)
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (engine.IMAGE_LIMIT + 1)
    try:
        with pytest.raises(RuntimeError):
            await event.deliver_image(
                "base64://" + base64.b64encode(big).decode(), local_Path_type=False
            )
    finally:
        engine.registry.sessions.pop(6, None)
        engine._attachments.clear()


# ---------- file_resolver 注入（webui 附件 → 工具可引用） ----------

def test_webui_event_injects_file_resolver(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    engine.save_attachment("data.csv", "text/csv", b"a,b\n1,2")
    try:
        event = engine.WebuiMessageEvent(9)
        resolver = event.get_extra("file_resolver")
        assert callable(resolver)

        segments = resolver(["data.csv", "missing.txt"])
        assert [s.file_name for s in segments] == ["data.csv"]
        assert Path(segments[0].url).is_file()
    finally:
        engine._attachments.clear()


@pytest.mark.asyncio
async def test_collect_context_file_segments_prefers_injected_resolver(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "upload_dir", lambda: tmp_path)
    engine.save_attachment("x.txt", "text/plain", b"X")

    class _FakeSandBox:
        pass

    class _FakeConfig:
        pass

    # run_code 及其 import 链在模块级取 SandBox/config 服务，测试环境给替身
    registered: list[str] = []
    for name, fake in (("SandBox", _FakeSandBox()), ("config", _FakeConfig())):
        if not container.exists(name):
            container.register(name, fake)
            registered.append(name)
    from atribot.LLMchat.tools.run_python_code.run_code import collect_context_file_segments

    try:
        event = engine.WebuiMessageEvent(11)
        segments = await collect_context_file_segments(event, ["x.txt", "y.txt"])
        assert [s.file_name for s in segments] == ["x.txt"]
    finally:
        engine._attachments.clear()
        for name in registered:
            container.unregister(name)


# ---------- 上下文序列化 ----------

def _make_context():
    from atribot.LLMchat.agent.context.context import AgentContext
    from atribot.LLMchat.agent.message import (
        AssistantMessage,
        ImageBase64Segment,
        TextSegment,
        ToolMessage,
        UserMessage,
    )

    ctx = AgentContext()
    ctx.append(UserMessage(content="你好"))
    ctx.append(UserMessage(content=[TextSegment("看这张图"), ImageBase64Segment("AAAA", "image/png")]))
    ctx.append(AssistantMessage(
        content="好的",
        reasoning_content="思考内容不应持久化",
        tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "web_search", "arguments": "{}"}}],
    ))
    ctx.append(ToolMessage(name="web_search", tool_call_id="call_1", content="搜索结果"))
    ctx.append(AssistantMessage(content="最终回答"))
    return ctx


def test_serialize_replaces_media_and_drops_reasoning():
    items = engine.serialize_context(_make_context())

    assert items[0] == {"role": "user", "content": "你好"}
    assert "看这张图" in items[1]["content"]
    assert "已省略" in items[1]["content"]
    assert "base64" not in items[1]["content"]

    assistant = items[2]
    assert assistant["content"] == "好的"
    assert assistant["tool_calls"][0]["function"]["name"] == "web_search"
    assert "reasoning_content" not in assistant

    assert items[3]["role"] == "tool"
    assert items[3]["tool_call_id"] == "call_1"


def test_serialize_deserialize_roundtrip():
    ctx = _make_context()
    items = engine.serialize_context(ctx)
    restored = engine.deserialize_context(items)

    assert [m.role for m in restored.messages] == ["user", "user", "assistant", "tool", "assistant"]
    assert restored.messages[0].content == "你好"
    assert restored.messages[2].tool_calls[0]["function"]["name"] == "web_search"
    assert restored.messages[3].content == "搜索结果"

    openai_list = restored.to_openai_list()
    assert openai_list[2]["role"] == "assistant"
    assert openai_list[3]["role"] == "tool"


# ---------- 用户消息构建 ----------

@pytest.mark.asyncio
async def test_build_user_content_text_only():
    content = await engine.build_user_content("hello", [], {"visual_sense": True})
    assert content == "hello"


@pytest.mark.asyncio
async def test_build_user_content_image_passthrough(monkeypatch):
    async def fake_convert(source, **kwargs):
        return SimpleNamespace(data="abc123", mime="image/jpeg", fmt="image/jpeg",
                               data_uri="data:image/jpeg;base64,abc123")

    # chat_engine 顶层导入了转换函数，需 patch 其命名空间内的绑定
    monkeypatch.setattr(engine, "url_to_image_jpeg", fake_convert)
    info = {"path": "/tmp/x.png", "name": "x.png", "kind": "image", "mime": "image/png"}

    content = await engine.build_user_content("看图", [info], {"visual_sense": True})
    assert isinstance(content, list)
    assert content[0].to_dict() == {"type": "text", "text": "看图"}
    assert content[1].to_dict() == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,abc123", "detail": "auto"},
    }


@pytest.mark.asyncio
async def test_build_user_content_image_downgrade_without_sense(monkeypatch):
    async def fake_convert(source, **kwargs):
        return SimpleNamespace(data="abc123", mime="image/jpeg", fmt="image/jpeg",
                               data_uri="data:image/jpeg;base64,abc123")

    monkeypatch.setattr(engine, "url_to_image_jpeg", fake_convert)
    info = {"path": "/tmp/x.png", "name": "x.png", "kind": "image", "mime": "image/png"}

    content = await engine.build_user_content("看图", [info], {"visual_sense": False})
    assert isinstance(content, list)
    assert content[1].to_dict()["type"] == "text"
    assert "[图片 x.png" in content[1].to_dict()["text"]


# ---------- 会话 id 分配与复用 ----------

@pytest.mark.asyncio
async def test_registry_allocates_sequential_ids():
    registry = engine.SessionRegistry()
    a = await registry.create()
    b = await registry.create()
    assert (a.id, b.id) == (1, 2)


@pytest.mark.asyncio
async def test_registry_reuses_freed_lowest_id():
    registry = engine.SessionRegistry()
    a = await registry.create()
    await registry.create()
    await registry.create()
    await registry.delete(a.id)
    d = await registry.create()
    assert d.id == a.id


@pytest.mark.asyncio
async def test_registry_allocation_considers_db_rows(monkeypatch):
    async def fake_db_ids():
        return [1, 3]

    monkeypatch.setattr(engine, "db_list_ids", fake_db_ids)
    registry = engine.SessionRegistry()
    session = await registry.create()
    assert session.id == 2


@pytest.mark.asyncio
async def test_registry_busy_guard_and_delete_broadcast():
    registry = engine.SessionRegistry()
    session = await registry.create()
    queue = session.subscribe()

    session.task = SimpleNamespace(done=lambda: False, cancel=lambda: None)  # 模拟运行中的任务
    assert session.running is True

    await registry.delete(session.id)
    message = queue.get_nowait()
    assert message["type"] == "deleted"
    assert registry.get(session.id) is None


# ---------- 展示时间线重建 ----------

def test_timeline_from_row_groups_tools_with_answer():
    rows = [
        {"role": "user", "content": "查天气"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "name": "web_search", "content": "晴 26 度"},
        {"role": "assistant", "content": "今天晴，26 度"},
        {"role": "user", "content": "谢谢"},
    ]
    timeline = engine._timeline_from_row(rows)

    assert timeline[0] == {"type": "user", "text": "查天气", "files": [], "nonce": ""}
    assert timeline[1]["type"] == "assistant"
    assert timeline[1]["text"] == "今天晴，26 度"
    assert timeline[1]["tools"][0]["name"] == "web_search"
    assert timeline[2]["type"] == "user"


# ---------- 编辑回退 ----------

def _session_with_dialog():
    session = engine.ChatSession(1)
    session.context.add_user_message("第一问")
    session.context.add_assistant_message(content="第一答")
    session.context.add_user_message("第二问")
    session.append_user_timeline("第一问", [])
    session.append_assistant_timeline({"text": "第一答", "tools": [], "usage": None})
    session.append_user_timeline("第二问", [])
    return session


def test_edit_user_message_truncates_and_replaces():
    session = _session_with_dialog()

    assert engine.edit_user_message(session, 0, "改过的第一问") is True

    roles = [m.role for m in session.context.messages]
    assert roles == ["user"]
    assert session.context.messages[0].content == "改过的第一问"

    assert [i["type"] for i in session.timeline] == ["user"]
    assert session.timeline[0]["text"] == "改过的第一问"


def test_edit_user_message_keeps_media_segments():
    from atribot.LLMchat.agent.message import ImageBase64Segment, TextSegment

    session = engine.ChatSession(2)
    session.context.add_user_message([TextSegment("看图"), ImageBase64Segment("AAAA", "image/png")])
    session.append_user_timeline("看图", [{"id": "f1", "kind": "image"}])

    assert engine.edit_user_message(session, 0, "换个说法") is True

    msg = session.context.messages[0]
    assert isinstance(msg.content, list)
    assert msg.content[0].to_dict()["text"] == "换个说法"
    assert any(seg.to_dict().get("type") == "image_url" for seg in msg.content)


def test_edit_user_message_rejects_invalid_index():
    session = _session_with_dialog()
    assert engine.edit_user_message(session, 5, "x") is False
    assert engine.edit_user_message(session, -1, "x") is False
    # 失败不改变现有内容
    assert len(session.context.messages) == 3


# ---------- 运行参数 ----------

def test_chat_parameter_kwargs_forces_stream():
    kwargs = engine._chat_parameter_kwargs()
    assert kwargs["stream"] is True
    assert "temperature" in kwargs
    assert "tool_choice" in kwargs


def test_chat_parameter_kwargs_merges_overrides():
    kwargs = engine._chat_parameter_kwargs({
        "temperature": 0.2,
        "top_p": 0.5,
        "max_tokens": 1024,
        "tool_choice": "required",
    })
    assert kwargs["temperature"] == 0.2
    assert kwargs["top_p"] == 0.5
    assert kwargs["max_tokens"] == 1024
    assert kwargs["tool_choice"] == "required"
    assert kwargs["stream"] is True


def test_chat_parameter_kwargs_rejects_invalid_overrides():
    kwargs = engine._chat_parameter_kwargs({
        "temperature": 9,          # 超出 [0,2]
        "top_p": "abc",            # 非数值
        "max_tokens": -5,          # 超出 [1,200000]
        "tool_choice": "yolo",     # 非法枚举
        "hack": 1,                 # 未支持键
    })
    assert kwargs["temperature"] == 0.6
    assert kwargs["top_p"] == 0.9
    assert kwargs["max_tokens"] == 65536
    assert kwargs["tool_choice"] == "auto"
    assert "hack" not in kwargs
    assert kwargs["stream"] is True


# ---------- 会话标题 ----------

async def test_list_overview_includes_title(monkeypatch):
    import json as _json

    rows = [{
        "user_id": 2,
        "play_role": None,
        "total_tokens": 0,
        "last_updated": "",
        "context_data": _json.dumps([
            {"role": "user", "content": "帮我查一下明天\n的天气"},
            {"role": "assistant", "content": "好的"},
        ]),
    }]

    class _FakeDB:
        async def execute_SQL(self, sql, args=None):
            return rows

    monkeypatch.setattr(engine, "_db", lambda: _FakeDB())
    items = await engine.SessionRegistry().list_overview()
    assert len(items) == 1
    assert items[0]["id"] == 2
    assert items[0]["title"] == "帮我查一下明天 的天气"


# ---------- 头像端点 ----------

def _avatar_env(tmp_path, monkeypatch, with_image=True):
    """把 chat 路由的鉴权/配置依赖换成替身，config 指向临时目录"""
    from atribot.web_panel.routes import chat as chat_routes

    if with_image:
        (tmp_path / "ATRI-bot.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    monkeypatch.setattr(chat_routes, "_access_token", lambda: "t0k")
    monkeypatch.setattr(chat_routes, "_auth_rate_limited", lambda ip: None)
    monkeypatch.setattr(chat_routes, "_register_auth_failure", lambda ip: None)
    monkeypatch.setattr(chat_routes, "_clear_auth_failures", lambda ip: None)
    monkeypatch.setattr(chat_routes, "_cfg", lambda: SimpleNamespace(config_file_path=str(tmp_path / "config.json")))
    return chat_routes


@pytest.mark.asyncio
async def test_avatar_serves_image_beside_config(tmp_path, monkeypatch):
    routes = _avatar_env(tmp_path, monkeypatch)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    resp = await routes.api_chat_avatar(request, token="t0k")

    assert resp.media_type == "image/png"
    assert Path(resp.path).read_bytes() == b"\x89PNG\r\n\x1a\nfake"


@pytest.mark.asyncio
async def test_avatar_404_when_no_image(tmp_path, monkeypatch):
    from fastapi import HTTPException

    routes = _avatar_env(tmp_path, monkeypatch, with_image=False)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    with pytest.raises(HTTPException) as exc:
        await routes.api_chat_avatar(request, token="t0k")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_avatar_rejects_bad_token(tmp_path, monkeypatch):
    from fastapi import HTTPException

    routes = _avatar_env(tmp_path, monkeypatch)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    with pytest.raises(HTTPException) as exc:
        await routes.api_chat_avatar(request, token="wrong")
    assert exc.value.status_code == 401


# ---------- 面板品牌图端点（免鉴权，登录页/favicon 用） ----------

@pytest.mark.asyncio
async def test_panel_logo_serves_image_without_token(tmp_path, monkeypatch):
    routes = _avatar_env(tmp_path, monkeypatch)

    resp = await routes.api_panel_logo()

    assert resp.media_type == "image/png"
    assert Path(resp.path).read_bytes() == b"\x89PNG\r\n\x1a\nfake"


@pytest.mark.asyncio
async def test_panel_logo_404_when_no_image(tmp_path, monkeypatch):
    from fastapi import HTTPException

    routes = _avatar_env(tmp_path, monkeypatch, with_image=False)

    with pytest.raises(HTTPException) as exc:
        await routes.api_panel_logo()
    assert exc.value.status_code == 404


# ---------- 时间线时间戳 ----------

def test_append_user_timeline_returns_and_stores_ts():
    session = engine.ChatSession(1)

    ts = session.append_user_timeline("几点了", [], "n1")

    assert isinstance(ts, float) and ts > 0
    assert session.timeline[-1]["ts"] == ts
