"""QQ 官方机器人发送客户端

把项目内部的 ``SendMessage`` / CQ 码 / OneBot 消息段转换成官方 API 的
``msg_type`` / ``content`` / ``media`` 请求。

关键行为：

- 被动回复：官方要求带上入站消息的 ``msg_id``（5 分钟内、同一条消息有次数上限），
  这里按“会话最近一条入站消息”自动复用，用完退回主动消息（需显式开启）
- 富媒体：先 ``POST /v2/{groups|users}/{id}/files`` 上传（url 或 base64 file_data），
  再用 ``msg_type=7`` + ``media.file_info`` 发送
- 官方没有的能力（禁言 / 戳一戳 / 贴表情 / 合并转发 / 群成员查询等）统一安全 no-op
"""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Any, Optional

from atribot.core.atri_config import FilePathConfig, atriConfig
from atribot.core.logger import get_named_logger
from atribot.core.platform.qqbot.api import QQBotApiClient, QQBotAPIError
from atribot.core.platform.qqbot.cq import parse_cq_string
from atribot.core.platform.qqbot.id_map import QQBotIdMapper
from atribot.core.platform.qqbot.translate import safe_int
from atribot.core.platform.send_client import LoginInfo, SendClientBase
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage

MEDIA_IMAGE = 1
"""富媒体类型：图片"""
MEDIA_VIDEO = 2
"""富媒体类型：视频"""
MEDIA_AUDIO = 3
"""富媒体类型：语音"""
MEDIA_FILE = 4
"""富媒体类型：文件"""

_SEGMENT_TO_MEDIA = {
    "image": MEDIA_IMAGE,
    "record": MEDIA_AUDIO,
    "video": MEDIA_VIDEO,
    "file": MEDIA_FILE,
}

_DEFAULT_FILE_NAMES = {
    MEDIA_IMAGE: "image.png",
    MEDIA_VIDEO: "video.mp4",
    MEDIA_AUDIO: "audio.silk",
    MEDIA_FILE: "file.bin",
}

_PASSIVE_TTL = 290.0
"""被动回复有效期（官方为 5 分钟，这里留一点余量）"""


@dataclass(slots=True)
class _PassiveTarget:
    raw_message_id: str
    event_id: str | None
    expire_at: float


class QQBotSendClient(SendClientBase):
    """QQ 官方机器人消息发送客户端"""

    def __init__(
        self,
        api: QQBotApiClient,
        id_mapper: QQBotIdMapper,
        *,
        log: Logger | None = None,
        text_chunk_size: int = 1500,
        max_passive_replies: int = 5,
        allow_proactive: bool = False,
        file_paths: FilePathConfig | None = None,
    ) -> None:
        self._api = api
        self._id_mapper = id_mapper
        self.log = log or get_named_logger("QQBotSend")
        self._text_chunk_size = max(int(text_chunk_size or 1500), 200)
        self._max_passive_replies = max(int(max_passive_replies or 5), 1)
        self._allow_proactive = allow_proactive

        if file_paths is None:
            try:
                file_paths = container.get_by_type(atriConfig).file_path
            except Exception:  # noqa: BLE001 - 测试环境可能没有容器
                file_paths = None
        self.file_paths = file_paths

        self._reply_targets: dict[str, _PassiveTarget] = {}
        self._seq_counters: dict[str, int] = {}
        self._message_targets: dict[int, tuple[str, str]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._login_info: LoginInfo | None = None

    # ================================================================ 入站登记
    def remember_inbound(
        self,
        *,
        kind: str,
        target_id: int,
        raw_message_id: str,
        event_id: str | None,
        openid: str,
    ) -> None:
        """登记一条入站消息，供后续被动回复使用

        Args:
            kind: ``"group"`` / ``"private"``
            target_id: 合成后的整数 ID（群号 / 用户号）
            raw_message_id: 官方消息 ID
            event_id: 官方事件 ID（可选）
            openid: 原始 group_openid / user_openid
        """
        if not raw_message_id:
            return
        now = time.time()
        if len(self._reply_targets) > 512:
            self._reply_targets = {
                key: value
                for key, value in self._reply_targets.items()
                if value.expire_at > now
            }

        self._reply_targets[self._target_key(kind, target_id)] = _PassiveTarget(
            raw_message_id=raw_message_id,
            event_id=event_id,
            expire_at=now + _PASSIVE_TTL,
        )
        self._id_mapper.to_id("message", raw_message_id)
        if openid:
            self._id_mapper.to_id("group" if kind == "group" else "user", openid)

    # ================================================================ 抽象接口
    async def send(self, message: SendMessage) -> Optional[dict]:
        """发送 GroupMessage / PrivateMessage"""
        if isinstance(message, GroupMessage):
            return await self.send_group_msg(message.group_id, message.data)
        if isinstance(message, PrivateMessage):
            return await self.send_private_msg(message.user_id, message.data)
        self.log.error("不支持的消息类型: %s", type(message))
        return None

    async def async_send(self, action: str, params: dict) -> Optional[dict]:
        """兼容 OneBot 风格的动作名，仅支持发送/撤回相关动作"""
        if action == "send_group_msg":
            return await self.send_group_msg(
                int(params.get("group_id") or 0), params.get("message") or ""
            )
        if action == "send_private_msg":
            return await self.send_private_msg(
                int(params.get("user_id") or 0), params.get("message") or ""
            )
        if action == "delete_msg":
            return await self.delete_msg(params.get("message_id") or 0)
        if action == "get_login_info":
            info = await self.get_login_info()
            return {"status": "ok", "data": dict(info) if info else {}}
        self.log.debug("QQ 官方适配器不支持动作 %s，已忽略", action)
        return None

    async def send_group_msg(self, group_id: int, message: str | list) -> Optional[dict]:
        """发送群聊消息"""
        openid = self._id_mapper.to_raw("group", group_id)
        if not openid:
            self.log.warning(
                "群 %s 尚未收到过官方消息，无法确定 group_openid，发送已跳过", group_id
            )
            return None
        return await self._send_to_target("group", group_id, openid, message)

    async def send_private_msg(
        self, user_id: int, message: str | list, auto_escape: bool = False
    ) -> Optional[dict]:
        """发送 C2C 私聊消息"""
        openid = self._id_mapper.to_raw("user", user_id)
        if not openid:
            self.log.warning(
                "用户 %s 尚未收到过官方消息，无法确定 user_openid，发送已跳过", user_id
            )
            return None
        return await self._send_to_target("private", user_id, openid, message)

    async def close(self) -> None:
        """释放发送客户端（HTTP 会话由适配器统一关闭）"""
        self._reply_targets.clear()
        self._seq_counters.clear()
        self._message_targets.clear()
        self._locks.clear()

    # ================================================================ 媒体发送
    async def send_group_pictures(
        self,
        group_id: int,
        url_img: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "group", group_id, url_img, MEDIA_IMAGE, default, local_Path_type, "img"
        )

    async def send_group_image(self, group_id: int, url_img: str) -> Optional[dict]:
        return await self.send_group_pictures(group_id, url_img, default=False, local_Path_type=True)

    async def send_group_video(
        self,
        group_id: int,
        url_video: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "group", group_id, url_video, MEDIA_VIDEO, default, local_Path_type, "video"
        )

    async def send_group_audio(
        self,
        group_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "group", group_id, url_audio, MEDIA_AUDIO, default, local_Path_type, "audio"
        )

    async def send_group_file(
        self,
        group_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "group",
            group_id,
            url_file,
            MEDIA_FILE,
            default,
            local_Path_type,
            "file",
            file_name=name,
        )

    async def send_personal_pictures(
        self,
        qq_id: int,
        url_img: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "private", qq_id, url_img, MEDIA_IMAGE, default, local_Path_type, "img"
        )

    async def send_personal_audio(
        self,
        qq_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "private", qq_id, url_audio, MEDIA_AUDIO, default, local_Path_type, "audio"
        )

    async def send_personal_file(
        self,
        qq_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        return await self._send_media_by_kind(
            "private",
            qq_id,
            url_file,
            MEDIA_FILE,
            default,
            local_Path_type,
            "file",
            file_name=name,
        )

    # ================================================================ 查询 / 撤回
    async def get_login_info(self) -> LoginInfo | None:
        """获取机器人自身账号信息（``GET /users/@me``）"""
        if self._login_info is not None:
            return self._login_info
        try:
            data = await self._api.get_me()
        except QQBotAPIError as exc:
            self.log.warning("获取机器人账号信息失败: %s", exc)
            return None

        raw_id = data.get("id")
        if raw_id is None:
            self.log.warning("获取机器人账号信息失败，响应缺少 id: %s", data)
            return None

        user_id = safe_int(raw_id, 0)
        if user_id == 0:
            self.log.warning("机器人 id 非数字，已忽略: %r", raw_id)
            return None

        self._login_info = LoginInfo(
            user_id=user_id,
            nickname=str(data.get("username") or ""),
        )
        return self._login_info

    async def delete_msg(self, message_id: int | str) -> Optional[dict]:
        """撤回消息（仅支持本适配器发送过的消息）"""
        try:
            synthetic_id = int(message_id)
        except (TypeError, ValueError):
            self.log.debug("撤回失败，消息 ID 非法: %r", message_id)
            return None

        target = self._message_targets.get(synthetic_id)
        if target is None:
            self.log.debug("撤回失败，未知的消息 ID: %s", synthetic_id)
            return None

        kind, openid = target
        if kind != "group":
            self.log.debug("QQ 官方接口不支持撤回 C2C 消息")
            return None

        raw_id = self._id_mapper.to_raw("message", synthetic_id)
        if not raw_id:
            return None

        try:
            return await self._api.delete_group_message(openid, raw_id)
        except QQBotAPIError as exc:
            self.log.warning("撤回消息失败: %s", exc)
            return None

    async def get_msg_details(self, message_id: int | str):
        """官方接口不提供按 ID 拉取消息，固定返回 None"""
        return None

    # ================================================================ 合并转发（降级）
    async def send_group_merge_text(
        self,
        group_id: int,
        message: str,
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        """官方无合并转发能力，降级为分片文本"""
        return await self.send_group_msg(group_id, message)

    async def send_private_merge_text(
        self,
        qq_id: int,
        message: str,
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        return await self.send_private_msg(qq_id, message)

    async def send_group_merge_forward(
        self,
        group_id: int,
        input_messages: list[list[dict]],
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        return await self.send_group_msg(group_id, _flatten_messages(input_messages))

    async def send_private_merge_forward(
        self,
        qq_id: int,
        input_messages: list[list[dict]],
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        return await self.send_private_msg(qq_id, _flatten_messages(input_messages))

    # ================================================================ 能力缺失（安全 no-op）
    async def send_poke(self, *args: Any, **kwargs: Any) -> dict | None:
        self.log.debug("QQ 官方适配器不支持戳一戳")
        return None

    async def set_msg_emoji_like(
        self, message_id: int | str, emoji_id: int, set: bool = True
    ) -> dict | None:
        self.log.debug("QQ 官方适配器不支持贴表情")
        return None

    async def set_input_status(self, user_id: int | str, event_type: int) -> dict | None:
        self.log.debug("QQ 官方适配器不支持输入状态")
        return None

    async def set_group_ban(
        self, group_id: int | str, user_id: int | str, duration: int = 1800
    ) -> dict | None:
        self.log.debug("QQ 官方适配器不支持禁言")
        return None

    async def set_group_add_request(
        self, flag: str, approve: bool, reason: str = ""
    ) -> dict | None:
        self.log.debug("QQ 官方适配器不支持处理加群请求")
        return None

    async def set_group_admin(
        self, group_id: int | str, user_id: int | str, enable: bool = True
    ) -> dict | None:
        return None

    async def set_group_special_title(
        self, group_id: int | str, user_id: int | str, special_title: str = ""
    ) -> dict | None:
        return None

    async def send_group_json(self, group_id: int, json_dict: dict) -> dict | None:
        self.log.debug("QQ 官方适配器不支持 JSON 卡片")
        return None

    async def send_group_music(
        self,
        group_id: int,
        type: str,
        id: str | None = None,
        url: str | None = None,
        image: str | None = None,
        singer: str | None = None,
        title: str | None = None,
        content: str | None = None,
    ) -> dict | None:
        self.log.debug("QQ 官方适配器不支持音乐卡片")
        return None

    async def send_personal_music(self, *args: Any, **kwargs: Any) -> dict | None:
        return None

    async def get_group_info(self, group_id: int) -> dict | None:
        return None

    async def get_group_info_ex(self, group_id: int | str) -> dict | None:
        return None

    async def get_group_list(self, no_cache: bool | None = None) -> list[dict] | None:
        return None

    async def get_group_member_list(
        self, group_id: int | str, no_cache: bool | None = None
    ) -> list[dict] | None:
        return None

    async def get_group_member_info(
        self, group_id: int | str, user_id: int | str, no_cache: bool | None = None
    ) -> dict | None:
        return None

    async def get_stranger_info(self, qq_id: int | str) -> dict | None:
        return None

    async def get_img_details(self, file_id: str) -> Any:
        return None

    async def get_recordg_details(self, file: str, file_id: str, out_format: str = "mp3") -> dict | None:
        return None

    async def get_essence_msg_list(self, group_id: int | str) -> list[dict] | None:
        return None

    async def set_essence_msg(self, message_id: int | str) -> dict | None:
        return None

    async def delete_essence_msg(self, message_id: int | str) -> dict | None:
        return None

    async def send_group_sign(self, group_id: int | str) -> dict | None:
        return None

    async def upload_image_to_qun_album(
        self, group_id: int | str, file: str, **kwargs: Any
    ) -> dict | None:
        return None

    async def set_qq_avatar(self, file: str, local_Path_type: bool = True) -> dict | None:
        return None

    async def set_self_longnick(self, long_nick: str) -> dict | None:
        return None

    async def send_like(self, user_id: int | str, times: int | str = 1) -> dict | None:
        return None

    async def set_friend_add_request(
        self, flag: str, approve: bool = True, remark: str = ""
    ) -> dict | None:
        return None

    async def send_qzone_msg(self, *args: Any, **kwargs: Any) -> dict | None:
        return None

    async def delete_qzone_msg(self, tid: str) -> dict | None:
        return None

    # ================================================================ 内部实现
    @staticmethod
    def _target_key(kind: str, target_id: int) -> str:
        return f"{kind}:{int(target_id)}"

    def _lock_for(self, target_key: str) -> asyncio.Lock:
        lock = self._locks.get(target_key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[target_key] = lock
        return lock

    async def _send_to_target(
        self, kind: str, target_id: int, openid: str, message: str | list
    ) -> Optional[dict]:
        segments = self._normalize_segments(message)
        if not segments:
            return None

        target_key = self._target_key(kind, target_id)
        explicit_raw_id: str | None = None
        for segment in segments:
            if segment.get("type") == "reply":
                explicit_raw_id = self._resolve_reply_id(segment.get("data", {}).get("id"))
                break

        last_result: Optional[dict] = None
        buffer: list[str] = []

        async with self._lock_for(target_key):
            async def flush_text() -> None:
                nonlocal last_result
                if not buffer:
                    return
                text = "".join(buffer)
                buffer.clear()
                if not text.strip():
                    return
                for chunk in _split_text(text, self._text_chunk_size):
                    result = await self._send_payload(
                        kind,
                        openid,
                        target_key,
                        content=chunk,
                        explicit_raw_id=explicit_raw_id,
                    )
                    if result is not None:
                        last_result = result

            for segment in segments:
                seg_type = segment.get("type")
                data = segment.get("data") or {}
                if seg_type == "text":
                    buffer.append(str(data.get("text") or ""))
                elif seg_type == "markdown":
                    buffer.append(str(data.get("markdown") or data.get("text") or ""))
                elif seg_type == "reply":
                    continue
                elif seg_type == "at":
                    self.log.debug("QQ 官方适配器暂不支持 @ 消息段，已忽略")
                elif seg_type in _SEGMENT_TO_MEDIA:
                    await flush_text()
                    result = await self._send_media_segment(
                        kind, openid, target_key, seg_type, data, explicit_raw_id
                    )
                    if result is not None:
                        last_result = result
                else:
                    self.log.debug("QQ 官方适配器忽略消息段类型: %s", seg_type)

            await flush_text()

        return last_result

    def _normalize_segments(self, message: str | list) -> list[dict[str, Any]]:
        if isinstance(message, str):
            return parse_cq_string(message)
        if isinstance(message, list):
            return [item for item in message if isinstance(item, dict)]
        return []

    def _resolve_reply_id(self, value: Any) -> str | None:
        """把 reply 段里的消息 ID（合成整数或原始字符串）还原成官方 msg_id"""
        if value is None:
            return None
        raw = self._id_mapper.to_raw("message", value)
        if raw:
            return raw
        text = str(value)
        return text or None

    def _acquire_passive(
        self, target_key: str, explicit_raw_id: str | None
    ) -> tuple[str | None, int]:
        """分配 msg_id / msg_seq；返回 (msg_id, msg_seq)"""
        raw_id = explicit_raw_id
        if raw_id is None:
            target = self._reply_targets.get(target_key)
            if target is not None:
                if target.expire_at > time.time():
                    raw_id = target.raw_message_id
                else:
                    self._reply_targets.pop(target_key, None)

        if raw_id is None:
            return None, 1

        next_seq = self._seq_counters.get(raw_id, 0) + 1
        if next_seq > self._max_passive_replies:
            self.log.warning(
                "消息 %s 的被动回复次数已达上限 %d，本轮改为主动消息/丢弃",
                raw_id,
                self._max_passive_replies,
            )
            return None, 1

        self._seq_counters[raw_id] = next_seq
        return raw_id, next_seq

    async def _send_payload(
        self,
        kind: str,
        openid: str,
        target_key: str,
        *,
        content: str | None = None,
        msg_type: int = 0,
        media: dict | None = None,
        explicit_raw_id: str | None = None,
    ) -> Optional[dict]:
        raw_msg_id, msg_seq = self._acquire_passive(target_key, explicit_raw_id)
        if raw_msg_id is None and not self._allow_proactive:
            self.log.warning(
                "会话 %s 没有可用的被动回复目标（5 分钟内无入站消息），且未开启主动消息，发送已跳过",
                target_key,
            )
            return None

        payload: dict[str, Any] = {"msg_type": msg_type, "msg_seq": msg_seq}
        if raw_msg_id:
            payload["msg_id"] = raw_msg_id
        if content is not None:
            payload["content"] = content
        if media is not None:
            payload["media"] = media

        try:
            if kind == "group":
                response = await self._api.send_group_message(openid, payload)
            else:
                response = await self._api.send_c2c_message(openid, payload)
        except QQBotAPIError as exc:
            self.log.warning("发送消息失败 (%s): %s", target_key, exc)
            return None

        self._remember_sent(message_id=response.get("id"), kind=kind, openid=openid)
        return response

    def _remember_sent(self, *, message_id: Any, kind: str, openid: str) -> None:
        if not message_id:
            return
        synthetic_id = self._id_mapper.to_id("message", str(message_id))
        if len(self._message_targets) > 1024:
            self._message_targets.clear()
        self._message_targets[synthetic_id] = (kind, openid)

    async def _send_media_segment(
        self,
        kind: str,
        openid: str,
        target_key: str,
        seg_type: str,
        data: dict[str, Any],
        explicit_raw_id: str | None,
    ) -> Optional[dict]:
        file_type = _SEGMENT_TO_MEDIA.get(seg_type, MEDIA_FILE)
        ref = str(data.get("url") or data.get("file") or "")
        return await self._send_media_ref(
            kind,
            openid,
            target_key,
            ref,
            file_type,
            explicit_raw_id=explicit_raw_id,
            file_name=data.get("name") or data.get("file_name"),
        )

    async def _send_media_by_kind(
        self,
        kind: str,
        target_id: int,
        ref: str,
        file_type: int,
        default: bool,
        local_Path_type: bool,
        base_dir: str,
        *,
        file_name: str | None = None,
    ) -> Optional[dict]:
        openid = self._id_mapper.to_raw("group" if kind == "group" else "user", target_id)
        if not openid:
            self.log.warning("目标 %s 尚未收到过官方消息，无法确定 openid", target_id)
            return None

        ref = self._resolve_ref(ref, default, local_Path_type, base_dir)
        target_key = self._target_key(kind, target_id)
        async with self._lock_for(target_key):
            return await self._send_media_ref(
                kind,
                openid,
                target_key,
                ref,
                file_type,
                explicit_raw_id=None,
                file_name=file_name,
            )

    def _resolve_ref(
        self, ref: str, default: bool, local_Path_type: bool, base_dir: str
    ) -> str:
        if default and self.file_paths is not None:
            base = getattr(self.file_paths, base_dir, None)
            if base is not None:
                ref = str(Path(base) / ref)
        if local_Path_type and not ref.startswith(("http://", "https://", "base64://", "file://")):
            ref = f"file://{ref}"
        return ref

    async def _send_media_ref(
        self,
        kind: str,
        openid: str,
        target_key: str,
        ref: str,
        file_type: int,
        *,
        explicit_raw_id: str | None = None,
        file_name: str | None = None,
    ) -> Optional[dict]:
        if not ref:
            self.log.warning("富媒体引用为空，发送已跳过")
            return None

        remote_url: str | None = None
        file_data: str | None = None
        resolved_name = file_name
        if not resolved_name and not ref.startswith("base64://"):
            try:
                resolved_name = Path(ref.split("://", 1)[-1]).name or None
            except (OSError, ValueError):
                resolved_name = None

        if ref.startswith(("http://", "https://")):
            remote_url = ref
        else:
            raw_bytes = await self._read_media_bytes(ref)
            if raw_bytes is None:
                return None
            file_data = base64.b64encode(raw_bytes).decode()
            if not resolved_name:
                resolved_name = _DEFAULT_FILE_NAMES.get(file_type, "file.bin")

        if file_type == MEDIA_FILE and not resolved_name:
            resolved_name = _DEFAULT_FILE_NAMES[MEDIA_FILE]

        try:
            media = await self._upload_media(
                kind,
                openid,
                file_type,
                url=remote_url,
                file_data=file_data,
                file_name=resolved_name,
            )
        except QQBotAPIError as exc:
            if file_type != MEDIA_AUDIO:
                self.log.warning("上传富媒体失败 (%s): %s", target_key, exc)
                return None
            # 语音格式不被接受时降级为普通文件发送
            self.log.warning("语音上传失败，降级为文件发送 (%s): %s", target_key, exc)
            try:
                media = await self._upload_media(
                    kind,
                    openid,
                    MEDIA_FILE,
                    url=remote_url,
                    file_data=file_data,
                    file_name=resolved_name or _DEFAULT_FILE_NAMES[MEDIA_AUDIO],
                )
            except QQBotAPIError as retry_exc:
                self.log.warning("上传媒体失败 (%s): %s", target_key, retry_exc)
                return None

        result = await self._send_payload(
            kind,
            openid,
            target_key,
            msg_type=7,
            media=media,
            explicit_raw_id=explicit_raw_id,
        )
        if result is None:
            self.log.warning("富媒体已上传但发送失败 (%s)", target_key)
        return result

    async def _upload_media(
        self,
        kind: str,
        openid: str,
        file_type: int,
        *,
        url: str | None,
        file_data: str | None,
        file_name: str | None,
    ) -> dict:
        name = file_name if file_type == MEDIA_FILE else None
        if kind == "group":
            return await self._api.upload_group_media(
                openid, file_type, url=url, file_data=file_data, file_name=name
            )
        return await self._api.upload_c2c_media(
            openid, file_type, url=url, file_data=file_data, file_name=name
        )

    async def _read_media_bytes(self, ref: str) -> bytes | None:
        try:
            if ref.startswith("base64://"):
                return base64.b64decode(ref[len("base64://"):])

            if ref.startswith(("http://", "https://")):
                return await self._api.download(ref)

            path_text = ref[len("file://"):] if ref.startswith("file://") else ref
            path = Path(path_text)
            if not path.is_file():
                self.log.warning("媒体文件不存在: %s", path)
                return None
            return path.read_bytes()
        except (OSError, ValueError) as exc:
            self.log.warning("读取媒体失败 (%s): %s", ref[:120], exc)
            return None


def _split_text(text: str, size: int) -> list[str]:
    """按长度切分文本，优先在换行处断开"""
    if size <= 0 or len(text) <= size:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > size:
        window = remaining[:size]
        cut = window.rfind("\n")
        if cut < size // 2:
            cut = size
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n") if cut < size else remaining[cut:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _flatten_messages(input_messages: list[list[dict]]) -> str:
    """把多节点合并转发降级为纯文本"""
    lines: list[str] = []
    for node in input_messages:
        parts: list[str] = []
        for segment in node:
            if not isinstance(segment, dict):
                continue
            seg_type = segment.get("type")
            data = segment.get("data") or {}
            if seg_type == "text":
                parts.append(str(data.get("text") or ""))
            elif seg_type == "image":
                parts.append(f"[图片 {data.get('file') or data.get('url') or ''}]")
            elif seg_type == "record":
                parts.append("[语音]")
            elif seg_type == "video":
                parts.append("[视频]")
            elif seg_type == "file":
                parts.append(f"[文件 {data.get('file') or ''}]")
        text = "".join(parts).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)
