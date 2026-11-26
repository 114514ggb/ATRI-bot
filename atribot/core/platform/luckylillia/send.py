import json
import logging
from typing import Optional
from urllib.parse import unquote

from atribot.core.platform.onebot.forward import fill_forward_content
from atribot.core.platform.onebot.message_event import OneBotMessageEvent
from atribot.core.platform.onebot.send import OneBotSendClient
from atribot.core.platform.send_client import ImageDetails
from atribot.core.type.onebot_event_types import OneBotEvent


class LuckyLilliaSendClient(OneBotSendClient):
    """LuckyLilliaBot(LLBot) 消息发送客户端

    LLBot 的 OneBot11 实现与 NapCat 的差异：

    * 正向 WS 没有 payload 上限，语音/文件可以直接走 WS，不依赖额外的 HTTP 端口；
    * 本地上传用绝对路径即可（``uri2local`` 会优先按本地路径处理），
      避免 ``file://`` 对 ``%``、``#`` 等字符的 URL 解析问题；
    * ``get_image`` 只接受 ``file``（文件名或 file_uuid），且默认会把文件下载到本地，
      这里统一传 ``download: false``，只刷新下载链接；
    * 语音详情 API 名为 ``get_record``（NapCat 为 ``get_recordg``）；
    * JSON 卡片要求 ``data.data`` 为 JSON 字符串。
    """

    def __init__(
        self,
        access_token: str = "",
        connection_type: str = "WebSocket_client",
        ws_connection: object | None = None,
        source_name: str = "",
        log: logging.Logger | None = None,
    ):
        super().__init__(
            access_token=access_token,
            connection_type=connection_type,
            ws_connection=ws_connection,
            log=log,
        )
        self.source_name = source_name or "luckylillia"

    @staticmethod
    def _to_local_path(source: str) -> str:
        """把 ``file://`` 形式归一化成 LLBot 可直接识别的本地路径"""
        if not source.startswith("file://"):
            return source
        path = unquote(source[len("file://"):])
        # file:///D:/x.jpg -> D:/x.jpg；file://D:/x.jpg -> D:/x.jpg
        if len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return path

    async def _resolve_file_url(
        self,
        url: str,
        default: bool = False,
        local_Path_type: bool = True,
        base_dir: str = "img",
    ) -> str:
        """解析文件地址

        LLBot 的 ``uri2local`` 会先判断 ``fs.existsSync``，因此本地文件直接传路径
        比 ``file://`` 更稳妥（文件名的 ``%``、``#`` 不会被当成 URL 转义符）。
        """
        if url.startswith(("http://", "https://", "base64://", "data:")):
            return url
        if default and self.file_paths:
            base = getattr(self.file_paths, base_dir, None)
            if base:
                url = str(base / url)
        return self._to_local_path(url)

    # ------------------------------------------------------------------
    # 富媒体：LLBot 的 WS 没有大小限制，统一走当前连接发送
    # ------------------------------------------------------------------

    async def send_group_audio(
        self,
        group_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        """发送群聊语音（LLBot 走 WS 直接发送）"""
        file_url = await self._resolve_file_url(url_audio, default, local_Path_type, base_dir="audio")
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "record", "data": {"file": file_url}}],
            },
        )

    async def send_group_file(
        self,
        group_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        """发送群文件（LLBot 走 WS 直接发送）"""
        raw_path = url_file
        if default and self.file_paths:
            raw_path = str(self.file_paths.file / url_file)
        data: dict = {"file": self._to_local_path(raw_path) if local_Path_type else raw_path}
        if name:
            data["name"] = name
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "file", "data": data}],
            },
        )

    async def send_personal_audio(
        self,
        qq_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> dict | None:
        """发送私聊语音（LLBot 走 WS 直接发送）"""
        file_url = await self._resolve_file_url(url_audio, default, local_Path_type, base_dir="audio")
        return await self.send_private_msg(
            qq_id,
            [{"type": "record", "data": {"file": file_url}}],
        )

    async def send_personal_file(
        self,
        qq_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送私聊文件（LLBot 走 WS 直接发送）"""
        raw_path = url_file
        if default and self.file_paths:
            raw_path = str(self.file_paths.file / url_file)
        data: dict = {"file": self._to_local_path(raw_path) if local_Path_type else raw_path}
        if name:
            data["name"] = name
        return await self.send_private_msg(
            qq_id,
            [{"type": "file", "data": data}],
        )

    # ------------------------------------------------------------------
    # API 差异
    # ------------------------------------------------------------------

    async def send_group_json(self, group_id: int, json_dict: dict | str) -> dict | None:
        """发送群 JSON 卡片消息

        LLBot 要求消息段 ``data.data`` 是 JSON 字符串，而 NapCat 直接接受对象。
        """
        payload = json_dict if isinstance(json_dict, str) else json.dumps(json_dict, ensure_ascii=False)
        return await self.send_group_msg(group_id, [{"type": "json", "data": {"data": payload}}])

    async def get_img_details(
        self,
        file: str | None = None,
        file_id: str | None = None,
    ) -> ImageDetails | None:
        """获取图片信息及下载链接

        LLBot 的 ``get_image`` 只接受 ``file``（文件名或 file_uuid），
        并且 ``download`` 默认为 true 会把图片下载到 LLBot 所在机器，
        这里显式传 false，只刷新会过期的 CDN 链接。
        """
        target = file or file_id
        if not target:
            return None
        resp = await self.async_send("get_image", {"file": target, "download": False})
        if isinstance(resp, dict) and resp.get("status") == "ok":
            return resp.get("data")
        return None

    async def get_recordg_details(
        self,
        file: str = "",
        file_id: str = "",
        out_format: str = "mp3",
    ) -> dict | None:
        """获取语音消息详情

        LLBot 的 API 名为 ``get_record``，且只接受 ``file``（文件名或 file_uuid）。
        """
        target = file or file_id
        if not target:
            return None
        return await self.async_send(
            "get_record",
            {"file": target, "out_format": out_format},
        )

    async def get_msg_details(self, message_id: int | str) -> OneBotMessageEvent | None:
        """获取消息详情

        引用的消息如果本身是合并转发，同样需要补全内容才能被 LLM 读取。
        """
        resp = await self.async_send("get_msg", {"message_id": message_id})
        data = resp.get("data") if isinstance(resp, dict) else None
        if not isinstance(data, dict):
            return None
        data = await fill_forward_content(self, data, self.log)
        try:
            event = OneBotEvent.from_dict(data)
        except Exception:
            self.log.warning("get_msg 返回内容无法解析: %s", str(data)[:200])
            return None
        return OneBotMessageEvent(event=event, send_client=self, source=self.source_name)
