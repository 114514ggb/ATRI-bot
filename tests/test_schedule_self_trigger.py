"""schedule_self_trigger 持久化调度器测试"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

import pytest

from atribot.core.platform.manager import PlatformManager
from atribot.core.platform.send_client import SendClientBase
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.chat import GroupChat, PrivateChat
from atribot.LLMchat.tools.schedule_self_trigger import trigger_scheduler as ts
from atribot.LLMchat.tools.schedule_self_trigger.trigger_scheduler import (
    ScheduledTrigger,
    SelfTriggerScheduler,
    format_remaining,
)


class _FakeSendClient(SendClientBase):
    """最小可用的发送客户端替身"""

    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, message: Any) -> Optional[dict]:
        self.sent.append(message)
        return {}

    async def async_send(self, action: str, params: dict) -> Optional[dict]:
        return {}

    async def send_group_msg(self, group_id: int, message: Any, **kwargs: Any) -> Optional[dict]:
        self.sent.append(message)
        return {}

    async def send_private_msg(self, user_id: int, message: Any, **kwargs: Any) -> Optional[dict]:
        self.sent.append(message)
        return {}

    async def close(self) -> None:
        return None


class _FakeAdapter:
    """最小适配器替身(鸭子类型, 提供 get_client)"""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_client(self) -> Any:
        return self._client


class _FakeGroupChat(GroupChat):
    """群聊替身: 绕过真实初始化, 只记录触发调用"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def step(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def prompt_structure(self, *args: Any, **kwargs: Any) -> Any:
        return None

    async def send_reply_message_separator(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def trigger_internal_thought(self, custom_prompt: str, event: Any) -> None:
        self.calls.append(custom_prompt)


class _FakePrivateChat(PrivateChat):
    """私聊替身: 绕过真实初始化, 只记录触发调用"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def step(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def prompt_structure(self, *args: Any, **kwargs: Any) -> Any:
        return None

    async def send_reply_message_separator(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def trigger_internal_thought(self, custom_prompt: str, event: Any) -> None:
        self.calls.append(custom_prompt)


@pytest.fixture()
def supervisor():
    """向容器注册真实的 TimeTriggerSupervisor(无需 start 即可 add_task)"""
    inst = TimeTriggerSupervisor()
    container.register("TimeTriggerSupervisor", inst)
    yield inst
    container.unregister("TimeTriggerSupervisor")


@pytest.fixture()
def fake_chats():
    group_chat = _FakeGroupChat()
    private_chat = _FakePrivateChat()
    container.register("fake_group_chat", group_chat)
    container.register("fake_private_chat", private_chat)
    yield group_chat, private_chat
    container.unregister("fake_group_chat")
    container.unregister("fake_private_chat")


@pytest.fixture(autouse=True)
def _clean_scheduler_service():
    container.unregister(ts.SCHEDULER_SERVICE_NAME)
    yield
    container.unregister(ts.SCHEDULER_SERVICE_NAME)


def _group_primeval(note: str = "测试") -> dict[str, Any]:
    """最小可用的群消息原始事件字典"""
    return {
        "post_type": "message",
        "message_type": "group",
        "time": int(time.time()),
        "self_id": 10000,
        "user_id": 123,
        "group_id": 456,
        "message_id": 1,
        "raw_message": note,
        "message": [{"type": "text", "data": {"text": note}}],
        "sender": {"user_id": 123, "nickname": "tester", "card": "", "role": "member"},
    }


def _make_record(delay: float = 3600.0, group_id: Optional[int] = 456) -> ScheduledTrigger:
    return ScheduledTrigger(
        record_id="0123456789abcdef0123456789abcdef",
        note="记得提醒我喝水",
        trigger_at=time.time() + delay,
        created_at=time.time(),
        source="napcat",
        group_id=group_id,
        user_id=123,
        timeout=120.0,
        primeval=_group_primeval(),
    )


def _write_store(path: Path, records: list[dict[str, Any]]) -> Path:
    store = path / "scheduled_triggers.json"
    store.write_text(
        json.dumps({"version": 1, "tasks": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return store


def _read_store(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["tasks"]


def _record_to_dict(record: ScheduledTrigger) -> dict[str, Any]:
    return record.to_dict()


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0 秒"),
        (45, "45 秒"),
        (125, "2 分钟5 秒"),
        (7200, "2 小时"),
        (-10, "0 秒"),
    ],
)
def test_format_remaining(seconds: float, expected: str) -> None:
    assert format_remaining(seconds) == expected


def test_record_roundtrip() -> None:
    record = _make_record()
    restored = ScheduledTrigger.from_dict(record.to_dict())
    assert restored is not None
    assert restored.record_id == record.record_id
    assert restored.note == record.note
    assert restored.trigger_at == record.trigger_at
    assert restored.group_id == record.group_id
    assert restored.primeval == record.primeval


@pytest.mark.parametrize(
    "data",
    [
        None,
        "not-a-dict",
        {},
        {"note": 1, "trigger_at": time.time(), "primeval": {}},
        {"note": "x", "trigger_at": "tomorrow", "primeval": {}},
        {"note": "x", "trigger_at": time.time(), "primeval": "nope"},
        {"note": "x", "trigger_at": time.time(), "primeval": {}, "group_id": "abc"},
    ],
)
def test_from_dict_rejects_invalid(data: Any) -> None:
    assert ScheduledTrigger.from_dict(data) is None


def test_load_creates_empty_store(tmp_path: Path) -> None:
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store)
    assert store.exists()
    assert _read_store(store) == []
    assert scheduler.list_pending() == []


def test_load_backs_up_corrupted_store(tmp_path: Path) -> None:
    store = tmp_path / "scheduled_triggers.json"
    store.write_text("{ this is not json", encoding="utf-8")

    scheduler = SelfTriggerScheduler(store_path=store)

    assert scheduler.list_pending() == []
    assert (tmp_path / "scheduled_triggers.json.bak").exists()
    assert _read_store(store) == []



@pytest.mark.asyncio
async def test_restore_registers_future_task(tmp_path: Path, supervisor: TimeTriggerSupervisor) -> None:
    store = _write_store(tmp_path, [_record_to_dict(_make_record(delay=3600.0))])
    scheduler = SelfTriggerScheduler(store_path=store)

    await scheduler.restore()
    await scheduler.restore()  # 幂等: 二次调用不应重复注册

    assert len(supervisor._task_map) == 1
    assert len(_read_store(store)) == 1
    task = next(iter(supervisor._task_map.values()))
    assert task.trigger_timestamp == pytest.approx(supervisor.now() + 3600.0, abs=5.0)
    assert task.kwargs == {"record_id": "0123456789abcdef0123456789abcdef"}


@pytest.mark.asyncio
async def test_restore_drops_overdue_beyond_grace(tmp_path: Path, supervisor: TimeTriggerSupervisor) -> None:
    store = _write_store(tmp_path, [_record_to_dict(_make_record(delay=-3600.0))])
    scheduler = SelfTriggerScheduler(store_path=store)

    await scheduler.restore()

    assert len(supervisor._task_map) == 0
    assert _read_store(store) == []
    assert scheduler.list_pending() == []


@pytest.mark.asyncio
async def test_restore_immediate_within_grace(tmp_path: Path, supervisor: TimeTriggerSupervisor) -> None:
    store = _write_store(tmp_path, [_record_to_dict(_make_record(delay=-60.0))])
    scheduler = SelfTriggerScheduler(store_path=store)

    await scheduler.restore()

    assert len(supervisor._task_map) == 1
    task = next(iter(supervisor._task_map.values()))
    # 宽限期内: 以约 1 秒的延迟补触发
    assert task.trigger_timestamp == pytest.approx(supervisor.now() + 1.0, abs=1.5)


# ---------------------------------------------------------------------- 调度


@pytest.mark.asyncio
async def test_schedule_persists_and_registers(tmp_path: Path, supervisor: TimeTriggerSupervisor) -> None:
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store)
    record = _make_record(delay=60.0)

    record_id = await scheduler.schedule(record)

    assert record_id == record.record_id
    assert len(supervisor._task_map) == 1
    stored = _read_store(store)
    assert len(stored) == 1
    assert stored[0]["record_id"] == record.record_id


@pytest.mark.asyncio
async def test_schedule_rejects_duplicate(tmp_path: Path, supervisor: TimeTriggerSupervisor) -> None:
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store)
    record = _make_record(delay=60.0)

    await scheduler.schedule(record)
    with pytest.raises(ValueError):
        await scheduler.schedule(record)


@pytest.mark.asyncio
async def test_schedule_rejects_when_over_limit(tmp_path: Path, supervisor: TimeTriggerSupervisor) -> None:
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store, max_tasks=1)

    await scheduler.schedule(_make_record(delay=60.0))
    with pytest.raises(ValueError):
        await scheduler.schedule(_make_record(delay=120.0))



@pytest.mark.asyncio
async def test_run_forgets_record_before_firing_group(
    tmp_path: Path,
    supervisor: TimeTriggerSupervisor,
    fake_chats,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_chat, _ = fake_chats
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store)
    record = _make_record(delay=3600.0)
    await scheduler.schedule(record)

    # 事件重建替换为固定返回, 聚焦验证分发行为
    sentinel_event = object()
    monkeypatch.setattr(scheduler, "_rebuild_event", lambda rec: sentinel_event)

    await scheduler._run(record.record_id)

    # at-most-once: 触发前记录已从文件删除
    assert _read_store(store) == []
    assert group_chat.calls == [record.note]


@pytest.mark.asyncio
async def test_run_dispatches_private_chat(
    tmp_path: Path,
    supervisor: TimeTriggerSupervisor,
    fake_chats,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, private_chat = fake_chats
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store)
    record = _make_record(delay=3600.0, group_id=None)
    await scheduler.schedule(record)

    monkeypatch.setattr(scheduler, "_rebuild_event", lambda rec: object())

    await scheduler._run(record.record_id)

    assert private_chat.calls == [record.note]
    assert _read_store(store) == []


@pytest.mark.asyncio
async def test_run_without_chat_service_does_not_raise(
    tmp_path: Path,
    supervisor: TimeTriggerSupervisor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """容器里没有对应聊天服务时只记日志, 不向外抛异常"""
    store = tmp_path / "scheduled_triggers.json"
    scheduler = SelfTriggerScheduler(store_path=store)
    record = _make_record(delay=3600.0)
    await scheduler.schedule(record)

    monkeypatch.setattr(scheduler, "_rebuild_event", lambda rec: object())

    original_get_by_type = ts.container.get_by_type

    def _raise_not_found(cls: type) -> Any:
        if cls in (GroupChat, PrivateChat):
            raise ValueError("not found")
        return original_get_by_type(cls)

    monkeypatch.setattr(ts.container, "get_by_type", _raise_not_found)

    await scheduler._run(record.record_id)
    assert _read_store(store) == []



def test_rebuild_event_with_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = SelfTriggerScheduler(store_path=tmp_path / "scheduled_triggers.json")

    manager = PlatformManager.__new__(PlatformManager)
    manager._adapters = {"napcat": _FakeAdapter(_FakeSendClient())}

    original_get_by_type = ts.container.get_by_type

    def fake_get_by_type(cls: type) -> Any:
        if cls is PlatformManager:
            return manager
        return original_get_by_type(cls)

    monkeypatch.setattr(ts.container, "get_by_type", fake_get_by_type)

    event = scheduler._rebuild_event(_make_record())

    assert event.group_id == 456
    assert event.user_id == 123
    assert event.source == "napcat"
    assert isinstance(event.send_client, SendClientBase)


def test_rebuild_event_without_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = SelfTriggerScheduler(store_path=tmp_path / "scheduled_triggers.json")

    manager = PlatformManager.__new__(PlatformManager)
    manager._adapters = {}

    monkeypatch.setattr(ts.container, "get_by_type", lambda cls: manager)

    with pytest.raises(RuntimeError):
        scheduler._rebuild_event(_make_record())


@pytest.mark.asyncio
async def test_get_scheduler_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_init(
        self: SelfTriggerScheduler,
        store_path: Optional[Path] = None,
        grace_seconds: Optional[float] = None,
        max_tasks: Optional[int] = None,
    ) -> None:
        self.log = logging.getLogger("test.SelfTrigger")
        self._store_path = Path(tmp_path) / "scheduled_triggers.json"
        self._tasks = {}
        self._task_ids = {}
        self._save_lock = asyncio.Lock()
        self._restored = True

    monkeypatch.setattr(ts.SelfTriggerScheduler, "__init__", fake_init)

    first = ts.get_scheduler()
    second = ts.get_scheduler()

    assert first is second
    assert container.exists(ts.SCHEDULER_SERVICE_NAME)
