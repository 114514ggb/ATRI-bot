import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Any, Optional

from atribot.core.platform.manager import PlatformManager
from atribot.core.platform.onebot.message_event import OneBotMessageEvent
from atribot.core.platform.send_client import SendClientBase
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.onebot_event_types import OneBotEvent
from atribot.LLMchat.chat import GroupChat, PrivateChat

DEFAULT_STORE_FILENAME = "scheduled_triggers.json"
"""默认的持久化文件名"""

DEFAULT_TASK_TIMEOUT = 120.0
"""单次触发执行的默认超时时间(秒)"""


def format_remaining(seconds: float) -> str:
    """把剩余秒数格式化为 'X小时Y分钟Z秒' 的可读文本"""
    seconds = max(float(seconds), 0.0)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    text = "".join([
        f"{h} 小时" if h else "",
        f"{m} 分钟" if m else "",
        f"{s} 秒" if s else "",
    ])
    return text or f"{seconds:.0f} 秒"


@dataclass(slots=True)
class ScheduledTrigger:
    """一条待触发的自触发任务持久化记录"""

    record_id: str
    """任务唯一标识(uuid4 hex), 跨重启稳定"""

    note: str
    """触发时传给自己的任务介绍(作为新一轮思考的输入)"""

    trigger_at: float
    """绝对触发时刻(Unix 墙上时间戳, 秒)"""

    created_at: float
    """任务创建时刻(Unix 墙上时间戳, 秒)"""

    source: str
    """来源平台标识(如 'napcat'), 用于重建发送客户端"""

    group_id: Optional[int]
    """目标群号; None 表示私聊触发"""

    user_id: Optional[int]
    """触发时关联的用户 QQ, 可为 None"""

    timeout: float
    """单次触发执行的超时时间(秒)"""

    primeval: dict[str, Any]
    """原始 OneBot 事件字典, 恢复时经 OneBotEvent.from_dict 重建事件对象"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "note": self.note,
            "trigger_at": self.trigger_at,
            "created_at": self.created_at,
            "source": self.source,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "timeout": self.timeout,
            "primeval": self.primeval,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional[ScheduledTrigger]:
        """从字典构建记录, 字段不合法时返回 None"""
        if not isinstance(data, dict):
            return None
        note = data.get("note")
        trigger_at = data.get("trigger_at")
        primeval = data.get("primeval")
        if not isinstance(note, str) or not isinstance(trigger_at, (int, float)) or not isinstance(primeval, dict):
            return None

        group_id = data.get("group_id")
        user_id = data.get("user_id")
        try:
            group_id = int(group_id) if group_id is not None else None
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            return None

        timeout = data.get("timeout")
        timeout = float(timeout) if isinstance(timeout, (int, float)) else DEFAULT_TASK_TIMEOUT

        return cls(
            record_id=str(data.get("record_id") or uuid.uuid4().hex),
            note=note,
            trigger_at=float(trigger_at),
            created_at=float(data.get("created_at") or time.time()),
            source=str(data.get("source") or ""),
            group_id=group_id,
            user_id=user_id,
            timeout=timeout,
            primeval=primeval,
        )


class SelfTriggerScheduler:
    """自触发任务的持久化调度器

    职责:
        - schedule(): 新任务落盘并注册进 TimeTriggerSupervisor
        - restore():  幂等地恢复 JSON 中的待触发任务(过期按宽限期规则处理)
        - _run():     到点后重建事件并分发给 GroupChat / PrivateChat

    Attributes:
        log: 命名子日志器
    """

    DEFAULT_GRACE_SECONDS = 300.0
    """默认宽限期(秒): 迟到不超过该值的任务仍会立即补触发一次"""

    DEFAULT_MAX_TASKS = 100
    """默认的同时持久化任务数量上限"""

    def __init__(
        self,
        store_path: Optional[Path] = None,
        grace_seconds: Optional[float] = None,
        max_tasks: Optional[int] = None,
    ) -> None:
        self.log: Logger = container.get_by_type(Logger).getChild("SelfTrigger")
        self._store_path: Path = (
            Path(store_path) if store_path is not None
            else Path(__file__).resolve().parent / DEFAULT_STORE_FILENAME
        )
        self._grace_seconds: float = float(
            grace_seconds if grace_seconds is not None else self.DEFAULT_GRACE_SECONDS
        )
        self._max_tasks: int = int(max_tasks if max_tasks is not None else self.DEFAULT_MAX_TASKS)

        self._tasks: dict[str, ScheduledTrigger] = {}
        """待触发记录索引: record_id -> 记录"""

        self._task_ids: dict[str, int] = {}
        """record_id -> TimeTriggerSupervisor 的 task_id(仅内存, 不持久化)"""

        self._save_lock = asyncio.Lock()
        """串行化 JSON 写入, 避免并发写坏文件"""

        self._restored: bool = False
        """restore() 幂等标志"""

        self._load()

    def _load(self) -> None:
        """从 JSON 加载待触发记录; 文件不存在则生成, 损坏则备份后重建"""
        path = self._store_path
        try:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                self._write_file([])
                self.log.info(f"持久化存储不存在, 已创建空文件: {path}")
                return

            raw = json.loads(path.read_text(encoding="utf-8"))
            skipped = 0
            for item in raw.get("tasks", []):
                record = ScheduledTrigger.from_dict(item)
                if record is None:
                    skipped += 1
                else:
                    self._tasks[record.record_id] = record
            if skipped:
                self.log.warning(f"持久化存储中有 {skipped} 条无法解析的记录, 已跳过")
            self.log.info(f"已从 {path} 加载 {len(self._tasks)} 条待触发任务")
        except Exception as e:
            backup_path = path.with_suffix(path.suffix + ".bak")
            self.log.exception(f"持久化存储解析失败: {e}, 将备份到 {backup_path} 并重建空文件")
            try:
                if path.exists():
                    os.replace(path, backup_path)
                self._write_file([])
            except Exception:
                self.log.exception("持久化存储备份/重建失败, 将以空状态继续运行")

    def _write_file(self, records: list[dict[str, Any]]) -> None:
        """原子写 JSON 文件(先写临时文件再 os.replace)"""
        tmp_path = self._store_path.with_suffix(self._store_path.suffix + ".tmp")
        payload = json.dumps({"version": 1, "tasks": records}, ensure_ascii=False, indent=2)
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, self._store_path)

    async def _persist(self) -> None:
        """带锁异步刷盘(写当前内存中的全部记录)"""
        async with self._save_lock:
            await asyncio.to_thread(
                self._write_file, [record.to_dict() for record in self._tasks.values()]
            )

    async def schedule(self, record: ScheduledTrigger) -> str:
        """登记一条新任务: 落盘 + 注册到调度器

        Args:
            record: 待登记的持久化记录

        Returns:
            str: 任务唯一标识 record_id

        Raises:
            ValueError: 持久化任务数量已达上限
        """
        if record.record_id in self._tasks:
            raise ValueError(f"任务 {record.record_id} 已存在, 请勿重复登记")

        if not self._restored:
            await self.restore()

        self._discard_overdue()
        if len(self._tasks) >= self._max_tasks:
            raise ValueError(f"持久化自触发任务数量已达上限({self._max_tasks}), 暂无法登记新任务")

        self._tasks[record.record_id] = record
        await self._persist()
        self._register(record)
        self.log.info(
            f"已登记持久化自触发任务 {record.record_id}"
            f"(群{record.group_id}/私{record.user_id}), 触发时刻: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.trigger_at))}"
        )
        return record.record_id

    async def restore(self) -> None:
        """恢复持久化任务(幂等), 供启动时与未来的批量恢复服务调用"""
        if self._restored:
            return
        self._restored = True

        if not self._tasks:
            self.log.info("没有待恢复的持久化自触发任务")
            await self._persist()
            return

        counts = {"scheduled": 0, "immediate": 0, "dropped": 0}
        for record in list(self._tasks.values()):
            counts[self._register(record)] += 1

        await self._persist()
        self.log.info(
            f"持久化自触发任务恢复完成: 恢复 {counts['scheduled']} 条, "
            f"宽限期内补触发 {counts['immediate']} 条, 过期丢弃 {counts['dropped']} 条"
        )

    def _register(self, record: ScheduledTrigger) -> str:
        """把记录注册进 TimeTriggerSupervisor

        Returns:
            str: 'scheduled'(正常注册) / 'immediate'(宽限期内补触发) / 'dropped'(过期丢弃)
        """
        delta = record.trigger_at - time.time()
        if delta < -self._grace_seconds:
            self._tasks.pop(record.record_id, None)
            self.log.warning(
                f"持久化任务 {record.record_id} 已过期超过宽限期"
                f"({-delta:.0f}s > {self._grace_seconds:.0f}s), 直接丢弃"
            )
            return "dropped"

        effective_delta = delta if delta > 1.0 else 1.0
        task_id: int = container.get_by_type(TimeTriggerSupervisor).add_task(
            func=self._run,
            trigger_delta=effective_delta,
            timeout=record.timeout,
            kwargs={"record_id": record.record_id},
            remarks=f"自触发(持久化) 群{record.group_id} 私{record.user_id}",
        )
        self._task_ids[record.record_id] = task_id
        return "scheduled" if delta > 1.0 else "immediate"

    def _discard_overdue(self) -> None:
        """清掉已超过宽限期的记录(仅内存, 不刷盘)"""
        deadline = time.time() - self._grace_seconds
        self._tasks = {
            record_id: record for record_id, record in self._tasks.items()
            if record.trigger_at >= deadline
        }

    async def _run(self, record_id: str) -> None:
        """到点触发: 先删记录并落盘(at-most-once), 再重建事件并分发思考流程"""
        record = self._tasks.pop(record_id, None)
        task_id = self._task_ids.pop(record_id, None)
        if task_id is not None:
            container.get_by_type(TimeTriggerSupervisor).remove_task(task_id)
        await self._persist()
        if record is None:
            self.log.warning(f"持久化任务 {record_id} 记录不存在, 跳过触发")
            return

        try:
            event = self._rebuild_event(record)
        except Exception as e:
            self.log.error(f"持久化任务 {record_id} 事件重建失败, 已放弃触发: {e}")
            return

        try:
            if record.group_id:
                group_chat = container.get_by_type(GroupChat)
                await group_chat.trigger_internal_thought(custom_prompt=record.note, event=event)
            else:
                private_chat = container.get_by_type(PrivateChat)
                await private_chat.trigger_internal_thought(custom_prompt=record.note, event=event)
        except Exception as e:
            self.log.exception(f"持久化任务 {record_id} 触发失败: {e}")

    def _rebuild_event(self, record: ScheduledTrigger) -> atriMessageEvent:
        """用持久化的原始事件字典与平台标识重建消息事件信封"""
        event = OneBotEvent.from_dict(record.primeval)
        return OneBotMessageEvent(
            event=event,
            send_client=self._resolve_send_client(record.source),
            source=record.source,
        )

    def _resolve_send_client(self, source: str) -> SendClientBase:
        """按来源平台解析发送客户端, 目标适配器不可用时回退到任一可用适配器"""
        manager = container.get_by_type(PlatformManager)
        adapter = manager.get_adapter(source)
        if adapter is not None:
            client = adapter.get_client()
            if isinstance(client, SendClientBase):
                return client

        for name, candidate in manager.adapters.items():
                client = candidate.get_client()
                if isinstance(client, SendClientBase):
                    self.log.warning(f"来源平台 '{source}' 不可用, 已回退到平台 '{name}'")
                    return client

        raise RuntimeError(f"没有可用的平台适配器来重建发送客户端(来源: {source!r})")

    def list_pending(self) -> list[dict[str, Any]]:
        """列出全部待触发任务(按触发时刻升序), 供查询命令使用"""
        now = time.time()
        return sorted(
            (
                {
                    "record_id": record.record_id,
                    "group_id": record.group_id,
                    "user_id": record.user_id,
                    "note": record.note,
                    "trigger_at": record.trigger_at,
                    "created_at": record.created_at,
                    "remaining_seconds": max(0.0, record.trigger_at - now),
                }
                for record in self._tasks.values()
            ),
            key=lambda item: item["trigger_at"],
        )


def get_scheduler() -> SelfTriggerScheduler:
    """获取(必要时创建)调度器单例"""
    
    try:
        return container.get_by_type(SelfTriggerScheduler)
    except Exception:
        pass

    scheduler = SelfTriggerScheduler()
    container.register("SelfTriggerScheduler", scheduler)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        scheduler.log.debug("当前无运行中的事件循环, 持久化任务恢复将推迟到首次调度时执行")
    else:
        scheduler.log.info("持久化自触发调度器已创建, 开始恢复待触发任务")
        loop.create_task(scheduler.restore())
    return scheduler
