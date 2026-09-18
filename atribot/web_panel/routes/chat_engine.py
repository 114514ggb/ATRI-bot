"""WebUI 聊天会话引擎：多会话管理、id 分配、chat_context 持久化与 SubAgentRunner 驱动

会话模型：
    - 每个会话是一个虚拟"私聊用户"，user_id 从 1 开始分配（保留区间 1~WEBUI_ID_MAX，
      真实 QQ 号远大于该区间，不会冲突），独立于 QQ 聊天。
    - 会话历史按 user_id 写入 chat_context 表（需先在 users 表落一条昵称行以满足外键），
      删除会话时同步删除数据库记录，释放的 id 会被新会话优先复用（取最小空闲 id）。
    - 数据库不可用（独立开发模式等）时自动退化为纯内存会话。

核心循环完全复用 SubAgentRunner.run()（stream=True），
事件经 to_dict() 序列化后广播给订阅了该会话的 WebSocket 连接。
"""

import asyncio
import json
import logging
import mimetypes
import secrets
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Union

from atribot.common_utils.file.file_utils import resolve_file_to_bytes
from atribot.common_utils.file.image_utils import url_to_image_jpeg
from atribot.common_utils.file.media_utils import url_to_audio_mp3, url_to_video_mp4
from atribot.core.platform.send_client import SendClientBase
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.chat_message_types import FileSegment as PlatformFileSegment
from atribot.LLMchat.agent.context.context import AgentContext
from atribot.LLMchat.agent.message import (
    AssistantMessage,
    AudioSegment,
    FileSegment,
    ImageBase64Segment,
    TextSegment,
    ToolMessage,
    UserMessage,
    VideoBase64Segment,
)

WEBUI_ID_MAX = 9999
"""WebUI 会话 user_id 保留区间上限（真实 QQ 号从 1 万起步，不会冲突）"""

MAX_TURNS = 20
"""单轮对话内 Agent 最大步数（与 sub_agent 工具一致）"""

WEBUI_PRESET = "webui"
"""聊天页默认使用的工具预设名（config.json tool_presets）"""

PERSONA_CUSTOM = "custom"
"""play_role 列中标记自定义人设的值（自定义人设全文只保存在浏览器本地）"""

IMAGE_LIMIT = 30 * 1024 * 1024
AUDIO_LIMIT = 50 * 1024 * 1024
VIDEO_LIMIT = 200 * 1024 * 1024
FILE_LIMIT = 100 * 1024 * 1024

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".avif"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".opus", ".silk", ".amr"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".m4v"}

log = logging.getLogger("atri-bot.WebChat")


# ---------- 附件仓库 ----------

_attachments: Dict[str, Dict[str, Any]] = {}
"""附件 id -> {path, name, mime, kind, size}（进程内注册表，文件落盘在临时目录）"""


def upload_dir() -> Path:
    try:
        root = Path(container.get("config").file_path.project_root)
    except Exception:
        root = Path.cwd()
    directory = root / "document" / "temp" / "webui_chat"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def classify_file(name: str, mime: str = "") -> str:
    """按扩展名/MIME 判定附件类别（image/audio/video/file）"""
    ext = Path(name).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"


def size_limit_for(kind: str) -> int:
    return {
        "image": IMAGE_LIMIT,
        "audio": AUDIO_LIMIT,
        "video": VIDEO_LIMIT,
        "file": FILE_LIMIT,
    }.get(kind, FILE_LIMIT)


def save_attachment(name: str, mime: str, data: bytes) -> Dict[str, Any]:
    """落盘一个附件并登记注册表，返回描述信息"""
    kind = classify_file(name, mime)
    att_id = secrets.token_hex(8)
    ext = Path(name).suffix.lower()[:10]
    path = upload_dir() / f"{att_id}{ext}"
    path.write_bytes(data)
    info = {
        "id": att_id,
        "path": str(path),
        "name": name or f"file{ext}",
        "mime": mime or "application/octet-stream",
        "kind": kind,
        "size": len(data),
    }
    _attachments[att_id] = info
    return info


def get_attachment(att_id: str) -> Optional[Dict[str, Any]]:
    return _attachments.get(att_id)


def purge_old_uploads(max_age_hours: float = 24.0) -> None:
    """清理超期的上传文件与注册表项（进程重启后注册表为空，靠 mtime 兜底删盘上残留）"""
    deadline = time.time() - max_age_hours * 3600
    for att_id, info in list(_attachments.items()):
        try:
            if Path(info["path"]).stat().st_mtime < deadline:
                Path(info["path"]).unlink(missing_ok=True)
                _attachments.pop(att_id, None)
        except OSError:
            continue
    try:
        for file in upload_dir().iterdir():
            try:
                if file.is_file() and file.stat().st_mtime < deadline:
                    file.unlink(missing_ok=True)
            except OSError:
                continue
    except OSError:
        pass


def attachment_brief(info: Dict[str, Any]) -> Dict[str, Any]:
    """附件的面向前端摘要（预览走 /api/chat/files/{id}）"""
    return {
        "id": info["id"],
        "name": info["name"],
        "kind": info["kind"],
        "mime": info["mime"],
        "size": info["size"],
        "url": f"/admin/api/chat/files/{info['id']}",
    }


# ---------- 合成消息事件 ----------

_MAGIC_EXT_SNIPPETS: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"fLaC", ".flac"),
    (b"OggS", ".ogg"),
    (b"ID3", ".mp3"),
)


def _sniff_ext(data: bytes) -> str:
    """按文件头魔数猜测扩展名（WebP/WAV/MP3 帧头需按偏移判断）"""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ".wav"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return ".mp3"
    for magic, ext in _MAGIC_EXT_SNIPPETS:
        if data.startswith(magic):
            return ext
    return ".bin"


class WebuiSendClient(SendClientBase):
    """WebUI 会话的发送客户端：出站媒体落盘为会话附件并广播到 WebSocket

    工具经 message_data.deliver_*（基类按群/私分流后进入 personal 系列）触达这里；
    文件复用聊天附件仓库（document/temp/webui_chat，24h 过期），
    前端凭 /api/chat/files/{id} 预览下载。发送文本类内容以 WebSocket 消息呈现。
    """

    def __init__(self, session_id: int) -> None:
        self.session_id = session_id

    def _session(self) -> "ChatSession":
        session = registry.get(self.session_id)
        if session is None:
            raise RuntimeError(f"WebUI 会话 #{self.session_id} 已不存在")
        return session

    # -- SendClientBase 抽象方法 --

    async def send(self, message) -> Optional[dict]:
        raise RuntimeError("WebUI 会话不支持 SendMessage 直发，请使用 deliver_* 系列")

    async def async_send(self, action: str, params: dict) -> Optional[dict]:
        raise RuntimeError(f"WebUI 会话不支持平台 API 调用: {action}")

    async def send_group_msg(self, group_id: int, message: str | list) -> Optional[dict]:
        raise RuntimeError("WebUI 会话不存在群聊目标")

    async def send_private_msg(
        self,
        user_id: int,
        message: str | list,
        auto_escape: bool = False,
    ) -> Optional[dict]:
        session = self._session()
        session.broadcast({"type": "assistant_note", "text": str(message)})
        return None

    async def close(self) -> None:
        return None

    # -- 富媒体投递 --

    async def _deliver_attachment(
        self,
        url: str,
        name: Optional[str],
        fallback_stem: str,
    ) -> Optional[dict]:
        """解析载荷（base64/本地路径/URL）→ 落盘附件 → 广播卡片，返回投递摘要"""
        session = self._session()
        try:
            resolved_name, data = await resolve_file_to_bytes(
                url, name or fallback_stem, max_bytes=FILE_LIMIT
            )
        except Exception as e:
            raise RuntimeError(f"文件载荷解析失败: {e}") from e
        if not Path(resolved_name).suffix:
            resolved_name += _sniff_ext(data)

        kind = classify_file(resolved_name)
        limit = size_limit_for(kind)
        if len(data) > limit:
            raise RuntimeError(
                f"文件超过 WebUI {kind} 附件限额 {limit // (1024 * 1024)}MB: {resolved_name}"
            )

        mime = mimetypes.guess_type(resolved_name)[0] or ""
        info = save_attachment(resolved_name, mime, data)
        brief = attachment_brief(info)
        session.pending_files.append(brief)
        session.broadcast({"type": "attachment", "file": brief})
        return {"file_id": info["id"], "name": resolved_name}

    async def send_personal_pictures(
        self,
        qq_id: int,
        url_img: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> Optional[dict]:
        return await self._deliver_attachment(url_img, None, "image.png")

    async def send_personal_audio(
        self,
        qq_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> Optional[dict]:
        return await self._deliver_attachment(url_audio, None, "audio.mp3")

    async def send_personal_file(
        self,
        qq_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        return await self._deliver_attachment(url_file, name, "file.bin")

    async def send_private_merge_text(
        self,
        qq_id: int,
        message: str,
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> Optional[dict]:
        session = self._session()
        session.broadcast({"type": "merge_text", "source": source, "message": message})
        return None

    async def send_personal_music(
        self,
        qq_id: int,
        type: str,
        id: str | None = None,
        url: str | None = None,
        image: str | None = None,
        singer: str | None = None,
        title: str | None = None,
        content: str | None = None,
    ) -> Optional[dict]:
        session = self._session()
        parts = [f"分享音乐[{type}]", title or id or url or ""]
        if singer:
            parts.append(f"歌手: {singer}")
        if url:
            parts.append(url)
        session.broadcast({"type": "assistant_note", "text": " · ".join(p for p in parts if p)})
        return None


def _attachment_file_resolver():
    """构造按文件名检索 WebUI 附件注册表的查找器

    注入到事件 extra（"file_resolver"）供 add_file / run_python_code 等工具消费：
    工具只感知"是否注入了查找器"，不感知 webui 平台本身。
    """

    def resolve(names: List[str]) -> List[PlatformFileSegment]:
        remaining = set(names or [])
        found: List[PlatformFileSegment] = []
        for info in _attachments.values():
            if info["name"] in remaining:
                remaining.discard(info["name"])
                found.append(PlatformFileSegment.from_local_path(
                    info["path"],
                    file_name=info["name"],
                    url=info["path"],
                    file_size=info["size"],
                ))
        return found

    return resolve


class WebuiMessageEvent(atriMessageEvent):
    """WebUI 会话的合成私聊消息信封：user_id=会话id、chat_scope=private

    真实事件由平台适配器构造，这里用最小事件桩提供 time/user_id/group_id 等字段，
    使 SubAgentRunner 与依赖 message_data 的工具按私聊语义工作；
    发送客户端为 WebuiSendClient（出站媒体投递回本会话的 WebSocket）。
    """

    def __init__(self, user_id: int) -> None:
        stub = SimpleNamespace(
            time=int(time.time()),
            user_id=user_id,
            group_id=None,
            is_at=False,
            message_id=None,
        )
        super().__init__(stub, send_client=WebuiSendClient(user_id), source="webui")
        self.set_extra("file_resolver", _attachment_file_resolver())


# ---------- 服务解析（惰性，保持面板可在不完整运行时安全导入） ----------

def get_supplier_manager():
    from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager

    return container.get_by_type(LLMConnectionManager)


def model_capabilities(supplier: str, model: str) -> Dict[str, bool]:
    """读取模型多模态能力标记；供应商/模型未知时全 False"""
    caps = {"visual_sense": False, "audio_sense": False, "video_sense": False}
    try:
        manager = get_supplier_manager()
        conn = manager.connections.get(supplier)
        info = (conn.model_dict.get(model) or {}) if conn is not None else {}
    except Exception:
        info = {}
    for key in caps:
        caps[key] = bool(info.get(key))
    return caps


def _get_media_processor():
    from atribot.LLMchat.media_processor import MediaProcessor

    return container.get_by_type(MediaProcessor)


def _tool_calls_service():
    if not container.exists("ToolCalls"):
        return None
    return container.get("ToolCalls")


# ---------- 用户消息构建（附件 → 消息段，与 QQ 管线同构） ----------

async def build_user_content(
    text: str,
    file_infos: List[Dict[str, Any]],
    caps: Dict[str, bool],
) -> Union[str, List[Any]]:
    """把文本与附件构建为 UserMessage.content

    有多模态能力时走压缩转换后的 base64 段；无能力时经 MediaProcessor 降级为文字描述。
    无附件时直接返回纯文本字符串。
    """
    if not file_infos:
        return text

    media_processor = None
    try:
        media_processor = _get_media_processor()
    except Exception:
        pass

    segments: List[Any] = [TextSegment(text)] if text else []

    for info in file_infos:
        path = info["path"]
        name = info["name"]
        kind = info["kind"]
        try:
            if kind == "image":
                result = await url_to_image_jpeg(path, file_name=name)
                if caps["visual_sense"]:
                    segments.append(ImageBase64Segment(result.data, result.mime))
                else:
                    desc = (
                        await media_processor.image_to_text(result.data_uri, name)
                        if media_processor else "图片（未配置识别模型）"
                    )
                    segments.append(TextSegment(f"[图片 {name} 描述: {desc}]"))
            elif kind == "audio":
                result = await url_to_audio_mp3(path, file_name=name)
                if caps["audio_sense"]:
                    segments.append(AudioSegment(result.data, result.fmt))
                else:
                    desc = (
                        await media_processor.audio_to_text(result.data_uri)
                        if media_processor else "音频（未配置识别模型）"
                    )
                    segments.append(TextSegment(f"[音频 {name} 转文字: {desc}]"))
            elif kind == "video":
                result = await url_to_video_mp4(path, file_name=name)
                if caps["video_sense"]:
                    segments.append(VideoBase64Segment(result.data, result.mime))
                else:
                    desc = (
                        await media_processor.video_to_text(result.data_uri)
                        if media_processor else "视频（未配置识别模型）"
                    )
                    segments.append(TextSegment(f"[视频 {name} 内容: {desc}]"))
            else:
                segments.append(TextSegment(f"[文件 {name}]"))
                segments.append(FileSegment(url=path, mime=info["mime"]))
        except Exception as e:
            log.warning("附件 %s (%s) 处理失败: %s", name, kind, e)
            segments.append(TextSegment(f"[附件 {name} 处理失败: {e}]"))

    return segments


# ---------- 上下文序列化（媒体不落库，防 JSONB 膨胀） ----------

def _stringify_segments(content) -> str:
    parts: List[str] = []
    for seg in content:
        seg_dict = seg.to_dict()
        if seg_dict.get("type") == "text":
            parts.append(seg_dict["text"])
        else:
            parts.append(f"[{seg_dict.get('type', 'media')} 已省略]")
    return "".join(parts)


def serialize_context(ctx) -> List[Dict[str, Any]]:
    """AgentContext -> chat_context.context_data 的 JSON 结构

    媒体段替换为文字注记、推理内容不落库；tool_calls 保留以便历史重建工具块。
    """
    from atribot.LLMchat.agent.message import (
        AssistantMessage,
        ToolMessage,
        UserMessage,
    )

    items: List[Dict[str, Any]] = []
    for msg in ctx.messages:
        if isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, str) else _stringify_segments(msg.content)
            items.append({"role": "user", "content": content})
        elif isinstance(msg, AssistantMessage):
            entry: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            items.append(entry)
        elif isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else _stringify_segments(msg.content)
            items.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
                "content": content,
            })
    return items


def deserialize_context(items: List[Dict[str, Any]]) -> "AgentContext":
    """chat_context.context_data -> AgentContext（推理内容不持久化，媒体为文字注记）"""

    ctx = AgentContext()
    for item in items or []:
        role = item.get("role")
        if role == "user":
            ctx.append(UserMessage(content=item.get("content", "")))
        elif role == "assistant":
            ctx.append(AssistantMessage(
                content=item.get("content") or "",
                tool_calls=item.get("tool_calls"),
            ))
        elif role == "tool":
            ctx.append(ToolMessage(
                name=item.get("name", ""),
                tool_call_id=item.get("tool_call_id", ""),
                content=item.get("content", ""),
            ))
    return ctx


# ---------- 数据库持久化（直连 database 服务，避开 ChatManager 热缓存） ----------

def _db():
    return container.get("database")


async def db_list_ids() -> List[int]:
    rows = await _db().execute_SQL(
        "SELECT user_id FROM chat_context WHERE user_id < $1", (WEBUI_ID_MAX,)
    )
    return sorted(int(r["user_id"]) for r in rows or [])


async def db_load(session_id: int) -> Optional[Dict[str, Any]]:
    rows = await _db().execute_SQL(
        "SELECT context_data, play_role, total_tokens, last_updated "
        "FROM chat_context WHERE user_id = $1",
        (session_id,),
    )
    if not rows:
        return None
    row = rows[0]
    context_data = row.get("context_data")
    if isinstance(context_data, str):
        context_data = json.loads(context_data)
    return {
        "context_data": context_data or [],
        "play_role": row.get("play_role"),
        "total_tokens": row.get("total_tokens") or 0,
        "last_updated": str(row.get("last_updated") or ""),
    }


async def db_save(session: "ChatSession") -> None:
    """users 落昵称行（满足外键）+ upsert chat_context；失败仅告警不中断"""
    items = serialize_context(session.context)
    total_tokens = session.context.count_estimate_tokens()
    play_role = session.persona_key or PERSONA_CUSTOM
    try:
        db = _db()
        await db.execute_SQL(
            "INSERT INTO users (user_id, nickname) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET nickname = EXCLUDED.nickname",
            (session.id, f"聊天{session.id}"),
        )
        await db.execute_SQL(
            "INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, play_role, last_updated) "
            "VALUES ($1, NULL, $2, $3, $4, CURRENT_TIMESTAMP) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "context_data = EXCLUDED.context_data, "
            "total_tokens = EXCLUDED.total_tokens, "
            "play_role = EXCLUDED.play_role, "
            "last_updated = CURRENT_TIMESTAMP",
            (session.id, json.dumps(items, ensure_ascii=False), total_tokens, play_role),
        )
    except Exception as e:
        log.warning("会话 %s 历史保存失败（将继续以内存会话运行）: %s", session.id, e)


async def db_delete(session_id: int) -> None:
    """删除会话的所有数据库痕迹（users 行级联清掉其余引用该 id 的记录）"""
    try:
        db = _db()
        await db.execute_SQL("DELETE FROM chat_context WHERE user_id = $1", (session_id,))
        await db.execute_SQL("DELETE FROM users WHERE user_id = $1", (session_id,))
    except Exception as e:
        log.warning("会话 %s 数据库记录删除失败: %s", session_id, e)


# ---------- 会话与注册表 ----------

class ChatSession:
    """一个 WebUI 聊天会话：独立 AgentContext + 事件广播 + 展示用时间线"""

    def __init__(self, session_id: int):
        from atribot.LLMchat.agent.context.context import AgentContext

        self.id: int = session_id
        self.context = AgentContext()
        self.persona_key: Optional[str] = None
        self.custom_persona: str = ""
        self.last_settings: Dict[str, Any] = {}
        self.timeline: List[Dict[str, Any]] = []
        """展示用历史（用户消息 / 每轮助手汇总），刷新与跨标签页恢复用"""
        self.task: Optional[asyncio.Task] = None
        self.listeners: Set[asyncio.Queue] = set()
        self.pending_files: List[Dict[str, Any]] = []
        """本轮工具投递的附件摘要（WebuiSendClient 写入，回合收尾并入时间线后清空）"""
        self.updated_at = time.time()

    # -- 订阅广播 --
    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self.listeners.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.listeners.discard(queue)

    def broadcast(self, message: Dict[str, Any]) -> None:
        self.updated_at = time.time()
        message.setdefault("session", self.id)
        for queue in list(self.listeners):
            queue.put_nowait(message)

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def touch(self) -> None:
        self.updated_at = time.time()

    def append_user_timeline(self, text: str, files: List[Dict[str, Any]], nonce: str = "") -> float:
        """入时间线并返回时间戳（秒），供 user_message 广播复用同一时钟"""
        ts = time.time()
        self.timeline.append({"type": "user", "text": text, "files": files, "nonce": nonce, "ts": ts})
        return ts

    def append_assistant_timeline(self, summary: Dict[str, Any]) -> None:
        self.timeline.append({"type": "assistant", **summary})


class SessionRegistry:
    """会话注册表：id 分配（最小空闲，含数据库占用）、创建/加载/删除"""

    def __init__(self) -> None:
        self.sessions: Dict[int, ChatSession] = {}

    async def allocate_id(self) -> int:
        used = set(self.sessions.keys())
        try:
            used.update(await db_list_ids())
        except Exception:
            pass  # 数据库不可用：仅按内存分配
        candidate = 1
        while candidate in used:
            candidate += 1
        if candidate > WEBUI_ID_MAX:
            raise RuntimeError(f"WebUI 会话数量已达上限 {WEBUI_ID_MAX}")
        return candidate

    async def create(self, persona_key: Optional[str] = None, custom_persona: str = "") -> ChatSession:
        session_id = await self.allocate_id()
        session = ChatSession(session_id)
        session.persona_key = persona_key
        session.custom_persona = custom_persona
        self.sessions[session_id] = session
        log.info("创建 WebUI 会话 #%s", session_id)
        return session

    def get(self, session_id: int) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    async def get_or_load(self, session_id: int) -> ChatSession:
        """取活动会话；不在内存则从数据库恢复（历史为文本注记形态）"""
        if not isinstance(session_id, int) or not (1 <= session_id <= WEBUI_ID_MAX):
            raise KeyError(f"非法会话 id: {session_id}")
        live = self.sessions.get(session_id)
        if live is not None:
            return live
        row = await db_load(session_id)
        if row is None:
            raise KeyError(f"会话 #{session_id} 不存在")
        session = ChatSession(session_id)
        session.context = deserialize_context(row["context_data"])
        marker = row.get("play_role") or ""
        if marker and marker != PERSONA_CUSTOM:
            session.persona_key = marker
        session.timeline = _timeline_from_row(row["context_data"])
        self.sessions[session_id] = session
        return session

    async def delete(self, session_id: int) -> None:
        session = self.sessions.get(session_id)
        if session is not None:
            if session.running:
                session.task.cancel()
            session.broadcast({"type": "deleted", "session": session_id})
            for queue in list(session.listeners):
                session.unsubscribe(queue)
            self.sessions.pop(session_id, None)
        await db_delete(session_id)
        log.info("删除 WebUI 会话 #%s（id 已释放可复用）", session_id)

    async def list_overview(self) -> List[Dict[str, Any]]:
        """活动会话 + 仅存数据库的会话合并清单（含展示标题）"""
        items: Dict[int, Dict[str, Any]] = {}
        try:
            rows = await _db().execute_SQL(
                "SELECT user_id, play_role, total_tokens, last_updated, context_data "
                "FROM chat_context WHERE user_id < $1 ORDER BY user_id",
                (WEBUI_ID_MAX,),
            )
            for row in rows or []:
                sid = int(row["user_id"])
                context_data = row.get("context_data")
                if isinstance(context_data, str):
                    try:
                        context_data = json.loads(context_data)
                    except (ValueError, TypeError):
                        context_data = []
                items[sid] = {
                    "id": sid,
                    "live": False,
                    "running": False,
                    "persona": row.get("play_role") or "",
                    "total_tokens": row.get("total_tokens") or 0,
                    "updated": str(row.get("last_updated") or ""),
                    "title": _context_title(context_data),
                }
        except Exception:
            pass
        for sid, session in self.sessions.items():
            entry = items.get(sid, {"id": sid, "persona": "", "total_tokens": 0, "updated": ""})
            entry.update({
                "live": True,
                "running": session.running,
                "persona": session.persona_key or PERSONA_CUSTOM,
                "total_tokens": session.context.count_estimate_tokens(),
                "updated": datetime.fromtimestamp(session.updated_at).strftime("%Y-%m-%d %H:%M:%S"),
                "title": _timeline_title(session.timeline),
            })
            items[sid] = entry
        return [items[k] for k in sorted(items)]


def _context_title(context_data: Optional[List[Dict[str, Any]]]) -> str:
    """从持久化消息提取展示标题（首条用户消息前 20 字）"""
    for item in context_data or []:
        if item.get("role") == "user":
            text = str(item.get("content") or "").strip().replace("\n", " ")
            if text:
                return text[:20]
    return ""


def _timeline_title(timeline: List[Dict[str, Any]]) -> str:
    """从展示时间线提取标题（与 _context_title 同构）"""
    for item in timeline:
        if item.get("type") == "user":
            text = str(item.get("text") or "").strip().replace("\n", " ")
            if text:
                return text[:20]
    return ""


def _timeline_from_row(context_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从持久化消息重建展示时间线（数据库形态：无媒体/思考内容）

    消息序列 user → assistant(tool_calls) → tool* → assistant(正文)，
    重建时把工具结果归入其后带正文的助手条目。
    """
    timeline: List[Dict[str, Any]] = []
    pending_tools: List[Dict[str, Any]] = []

    def flush_tools() -> None:
        nonlocal pending_tools
        if pending_tools:
            timeline.append({"type": "assistant", "text": "", "tools": pending_tools, "usage": None})
            pending_tools = []

    for item in context_data or []:
        role = item.get("role")
        if role == "user":
            flush_tools()
            timeline.append({"type": "user", "text": item.get("content", ""), "files": [], "nonce": ""})
        elif role == "assistant":
            text = item.get("content") or ""
            if text:
                timeline.append({"type": "assistant", "text": text, "tools": pending_tools, "usage": None})
                pending_tools = []
        elif role == "tool":
            pending_tools.append({
                "name": item.get("name", ""),
                "arguments": "",
                "result": item.get("content", ""),
                "is_error": False,
            })
    flush_tools()
    return timeline


registry = SessionRegistry()


# ---------- 人设与系统提示词 ----------

def resolve_persona_text(persona_key: Optional[str], custom_persona: str) -> str:
    """人设 key/自定义文本 -> 人设全文"""
    if not persona_key or persona_key == "none":
        return ""
    if persona_key == PERSONA_CUSTOM:
        return (custom_persona or "").strip()
    try:
        folder = Path(container.get("config").file_path.chat_manager)
        path = folder / f"{persona_key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    raise ValueError(f"人设 '{persona_key}' 不存在")


def build_system_prompt(session: ChatSession) -> str:
    """人设 + WebUI 环境说明 + 待发现工具提示"""
    persona = resolve_persona_text(session.persona_key, session.custom_persona)
    environment = (
        f"现在的时间是:{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n"
        f"对话以一对一私聊形式进行，会话用户user_id为{session.id}。"
        "当前为WebUI网页聊天环境:你通过工具发给用户的文件/图片会以可下载的附件卡片呈现,"
        "用户上传过的文件可通过add_file或run_python_code的files参数按文件名引用。"
    )
    prompt = f"{persona}\n\n{environment}".strip() if persona else environment
    tc = _tool_calls_service()
    if tc is not None:
        try:
            deferred_prompt = tc.get_deferred_tools_prompt(WEBUI_PRESET, chat_type="private")
            if deferred_prompt:
                prompt += f"\n{deferred_prompt}"
        except Exception:
            pass
    return prompt


# ---------- 单轮执行（SubAgentRunner 驱动） ----------

def _validate_param(key: str, value: Any) -> Optional[Any]:
    """校验单个请求参数覆盖项，非法时返回 None（丢弃）"""
    try:
        if key == "temperature":
            v = float(value)
            return v if 0 <= v <= 2 else None
        if key == "top_p":
            v = float(value)
            return v if 0 <= v <= 1 else None
        if key == "max_tokens":
            v = int(value)
            return v if 1 <= v <= 200000 else None
        if key == "tool_choice":
            return value if value in ("auto", "none", "required") else None
    except (TypeError, ValueError):
        return None
    return None


def _chat_parameter_kwargs(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """组装本轮 LLM 请求参数：配置默认 → 前端覆盖（逐项校验）→ 强制流式"""
    try:
        raw = container.get("config")._raw_config.get("model", {}).get("chat_parameter") or {}
        kwargs = dict(raw) if isinstance(raw, dict) else {}
    except Exception:
        kwargs = {}
    kwargs.setdefault("temperature", 0.6)
    kwargs.setdefault("top_p", 0.9)
    kwargs.setdefault("max_tokens", 65536)
    kwargs.setdefault("tool_choice", "auto")
    for key, value in (params or {}).items():
        parsed = _validate_param(key, value)
        if parsed is not None:
            kwargs[key] = parsed
    kwargs["stream"] = True  # 聊天页强制流式，覆盖配置中的 stream
    return kwargs


def _error_event(message: str, exception_type: str = "") -> Dict[str, Any]:
    """与 AgentError.to_dict() 同构的错误事件"""
    return {
        "event_type": "ERROR",
        "error_message": message,
        "exception_type": exception_type,
        "step_index": -1,
    }


def _broadcast_error(session: ChatSession, message: str, exception_type: str = "") -> None:
    """向会话订阅者广播错误事件（发送/重发两条路径共用）"""
    session.broadcast({"type": "event", "event": _error_event(message, exception_type)})


async def start_turn(
    session: ChatSession,
    text: str,
    file_ids: List[str],
    settings: Dict[str, Any],
    nonce: str = "",
) -> bool:
    """启动一轮对话；该会话已有任务在跑时返回 False（busy）"""
    if session.running:
        return False
    session.task = asyncio.create_task(
        _run_turn(session, text, file_ids, settings, nonce)
    )
    return True


async def start_regenerate(session: ChatSession, settings: Dict[str, Any]) -> bool:
    """编辑回退后的重发：上下文已就绪（末尾为用户消息），直接跑一轮 Agent"""
    if session.running:
        return False
    session.task = asyncio.create_task(_run_agent_turn(session, settings))
    return True


def _apply_persona_settings(session: ChatSession, settings: Dict[str, Any]) -> None:
    """会话级人设随本轮设置更新"""
    persona_key = settings.get("persona_key") or None
    if persona_key == PERSONA_CUSTOM:
        session.persona_key = None
        session.custom_persona = settings.get("custom_persona") or ""
    else:
        session.persona_key = persona_key
        session.custom_persona = ""


def _validate_model(supplier: str, model: str) -> None:
    """供应商/模型必须在 LLMConnectionManager 中可用"""
    manager = get_supplier_manager()
    conn = manager.connections.get(supplier)
    if conn is None:
        raise KeyError(f"供应商 '{supplier}' 不存在")
    if model not in (conn.model_dict or {}):
        raise KeyError(f"模型 '{model}' 不在供应商 '{supplier}' 的模型列表中")


def edit_user_message(session: ChatSession, um_index: int, text: str) -> bool:
    """编辑回退：截断到第 um_index 条用户消息（含）并替换其文本，同步时间线

    um_index 为该消息在全部用户消息中的序号（0 起）；
    多模态消息只替换文本段、保留媒体段（附件无需重传）；序号越界返回 False。
    """
    user_positions = [
        i for i, m in enumerate(session.context.messages)
        if isinstance(m, UserMessage)
    ]
    if not isinstance(um_index, int) or not (0 <= um_index < len(user_positions)):
        return False

    keep_upto = user_positions[um_index]
    target = session.context.messages[keep_upto]
    if isinstance(target.content, str):
        target.content = text
    else:
        media = [seg for seg in target.content if not isinstance(seg, TextSegment)]
        target.content = ([TextSegment(text)] if text else []) + media
    target.refresh_cache()

    new_messages = list(session.context.messages)[: keep_upto + 1]
    session.context._messages.clear()
    session.context._messages.extend(new_messages)

    new_timeline: List[Dict[str, Any]] = []
    seen = 0
    for item in session.timeline:
        if item.get("type") == "user":
            if seen == um_index:
                new_timeline.append({**item, "text": text})
                break
            seen += 1
        new_timeline.append(item)
    session.timeline = new_timeline
    return True


async def _run_turn(
    session: ChatSession,
    text: str,
    file_ids: List[str],
    settings: Dict[str, Any],
    nonce: str,
) -> None:
    session.touch()

    # 校验先行：无效配置不把用户消息写进上下文
    supplier = settings.get("supplier") or ""
    model = settings.get("model") or ""
    _apply_persona_settings(session, settings)
    try:
        _validate_model(supplier, model)
        resolve_persona_text(session.persona_key, session.custom_persona)  # 仅校验人设存在
    except Exception as e:
        _broadcast_error(session, f"配置无效: {e}", type(e).__name__)
        await _finish(session, "error")
        return

    file_infos = [info for fid in file_ids if (info := get_attachment(fid)) is not None]
    file_briefs = [attachment_brief(i) for i in file_infos]

    # 用户消息入上下文（附件按模型能力降级/直传）
    content = await build_user_content(text, file_infos, model_capabilities(supplier, model))
    session.context.add_user_message(content)
    user_ts = session.append_user_timeline(text, file_briefs, nonce)
    session.broadcast({
        "type": "user_message",
        "nonce": nonce,
        "text": text,
        "files": file_briefs,
        "ts": user_ts,
    })

    try:
        await _run_agent(session, settings)
    finally:
        session.task = None


async def _run_agent_turn(session: ChatSession, settings: Dict[str, Any]) -> None:
    """重发路径的任务壳：保证任务位清理与 _run_turn 一致"""
    try:
        await _run_agent(session, settings)
    finally:
        session.task = None


async def _run_agent(session: ChatSession, settings: Dict[str, Any]) -> None:
    """跑一轮 Agent 循环（上下文末尾应为用户消息）：校验→提示词→参数→流式事件→落库"""
    from atribot.LLMchat.agent.agent_data import AgentData
    from atribot.LLMchat.agent.runners.subagent.sub_agent_runner import SubAgentRunner

    session.touch()
    session.last_settings = settings
    _apply_persona_settings(session, settings)
    turn_started = time.monotonic()

    supplier = settings.get("supplier") or ""
    model = settings.get("model") or ""
    tools = settings.get("tools")  # None -> 用 webui 预设；[] -> 无工具

    try:
        try:
            _validate_model(supplier, model)
        except Exception as e:
            _broadcast_error(session, f"模型配置无效: {e}", type(e).__name__)
            await _finish(session, "error")
            return

        # 系统提示词（人设 + 环境 + 待发现工具）
        try:
            session.context.play_role = build_system_prompt(session)
        except ValueError as e:
            _broadcast_error(session, str(e), "ValueError")
            await _finish(session, "error")
            return

        kwargs = _chat_parameter_kwargs(settings.get("params"))
        agent_data = AgentData(
            context=session.context,
            model_name=model,
            supplier=supplier,
            tools=tools or [],
            tool_preset=WEBUI_PRESET if tools is None else None,
            kwargs=kwargs,
        )
        try:
            runner = SubAgentRunner(
                agent_data=agent_data,
                message_data=WebuiMessageEvent(session.id),
            )
        except Exception as e:
            _broadcast_error(session, f"Agent 初始化失败: {e}", type(e).__name__)
            await _finish(session, "error")
            return

        finish_reason = "completed"
        tools_summary: List[Dict[str, Any]] = []
        total_text = ""
        total_usage: Optional[Dict[str, Any]] = None
        try:
            async for event in runner.run(max_turns=MAX_TURNS):
                payload = event.to_dict()
                session.broadcast({"type": "event", "event": payload})
                name = payload.get("event_type")
                if name == "RUN_SUMMARY":
                    finish_reason = payload.get("finish_reason", finish_reason)
                    total_usage = payload.get("total_usage")
                    if payload.get("total_content"):
                        total_text = payload["total_content"]
                elif name == "STEP_SUMMARY":
                    if payload.get("content"):
                        total_text += payload["content"]
                    for tc_info in payload.get("tool_calls") or []:
                        tools_summary.append({
                            "name": tc_info.get("name", ""),
                            "arguments": tc_info.get("arguments", ""),
                            "result": tc_info.get("result", ""),
                            "is_error": bool(tc_info.get("is_error")),
                        })
                elif name == "ERROR":
                    finish_reason = "error"
        except asyncio.CancelledError:
            _broadcast_error(session, "已手动停止生成", "CancelledError")
            session.append_assistant_timeline({
                "text": total_text,
                "tools": tools_summary,
                "files": list(session.pending_files),
                "usage": None,
                "duration": round(time.monotonic() - turn_started, 1),
                "finish_reason": "stopped",
                "ts": time.time(),
            })
            session.pending_files.clear()
            try:
                await _finish(session, "stopped", round(time.monotonic() - turn_started, 1))
            except asyncio.CancelledError:
                pass
            raise
        except Exception as e:
            log.exception("WebUI 会话 #%s 运行异常", session.id)
            finish_reason = "error"
            _broadcast_error(session, str(e), type(e).__name__)

        duration = round(time.monotonic() - turn_started, 1)
        session.append_assistant_timeline({
            "text": total_text,
            "tools": tools_summary,
            "files": list(session.pending_files),
            "usage": total_usage,
            "duration": duration,
            "finish_reason": finish_reason,
            "ts": time.time(),
        })
        session.pending_files.clear()
        await _finish(session, finish_reason, duration)
    except Exception as e:
        # 兜底：循环之外的未预期异常（AgentData 构造等）也通知前端并正常收尾；
        # CancelledError 继承自 BaseException，不会被这里吞掉
        log.exception("WebUI 会话 #%s Agent 执行异常", session.id)
        _broadcast_error(session, str(e), type(e).__name__)
        await _finish(session, "error")


async def _finish(session: ChatSession, finish_reason: str, duration: Optional[float] = None) -> None:
    try:
        await db_save(session)
    finally:
        session.broadcast({
            "type": "done",
            "finish_reason": finish_reason,
            "duration": duration,
            "ts": time.time(),
        })
