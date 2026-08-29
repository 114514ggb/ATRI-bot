import logging
from typing import Literal, Optional

import aiohttp

from atribot.core.atri_config import FilePathConfig, atriConfig
from atribot.core.platform.send_client import ImageDetails, SendClientBase
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage
from atribot.core.type.onebot_event_types import OneBotEvent

from .connection import OneBotWSClient, OneBotWSServer
from .message_event import OneBotMessageEvent


class OneBotSendClient(SendClientBase):
    """OneBot 消息发送客户端"""

    def __init__(
        self,
        access_token: str = "ATRI",
        http_base_url: str = "http://localhost:8080",
        connection_type: Literal["http", "WebSocket_client", "WebSocket_server"] = "http",
        ws_connection: OneBotWSClient | OneBotWSServer | None = None,
        log: logging.Logger | None = None,
        file_paths: FilePathConfig | None = None,
    ):
        self.access_token = access_token
        self.http_base_url = http_base_url
        self.connection_type = connection_type
        self._ws = ws_connection
        self.log = log or logging.getLogger("OneBotSendClient")

        if file_paths is None:
            try:
                config = container.get_by_type(atriConfig)
                self.file_paths: FilePathConfig = config.file_path
            except Exception:
                self.file_paths: FilePathConfig | None = None
        else:
            self.file_paths = file_paths

        self._http_session: Optional[aiohttp.ClientSession] = None
        if connection_type == "http":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }
            self._http_session = aiohttp.ClientSession(headers=headers)
            self._send_impl = self._send_http
        else:
            self._send_impl = self._send_ws

        self.log.info("发送客户端已就绪 (模式: %s)", connection_type)

    async def _send_http(self, action: str, params: dict) -> Optional[dict]:
        """通过 HTTP POST 发送"""
        try:
            async with self._http_session.post(
                f"{self.http_base_url}/{action}", json=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.log.warning(
                        "HTTP 发送失败: %d %s", response.status, await response.text()
                    )
                    return None
        except aiohttp.ClientError as e:
            self.log.error("HTTP 请求异常: %s", e)
            return None

    async def _send_ws(self, action: str, params: dict) -> Optional[dict]:
        """通过 WebSocket 发送"""
        message = {
            "action": action,
            "params": params,
        }
        try:
            return await self._ws.send(message, with_echo=True)
        except Exception as e:
            self.log.error("WS 发送失败: %s", e)
            return None

    async def send(self, message: SendMessage) -> Optional[dict]:
        """发送消息对象

        Args:
            message: GroupMessage 或 PrivateMessage 实例

        Returns:
            API 响应字典，或 None
        """
        if isinstance(message, GroupMessage):
            action = "send_group_msg"
        elif isinstance(message, PrivateMessage):
            action = "send_private_msg"
        else:
            self.log.error("不支持的消息类型: %s", type(message))
            return None

        return await self._send_impl(action, message.to_dict())

    async def async_send(self, action: str, params: dict) -> Optional[dict]:
        """通用的发送请求

        Args:
            action: OneBot API 动作名称
            params: 请求参数字典

        Returns:
            API 响应字典，或 None
        """
        return await self._send_impl(action, params)

    async def send_group_msg(
        self,
        group_id: int,
        message: str | list,
    ) -> Optional[dict]:
        """发送群聊消息

        Args:
            group_id: 目标群号
            message: 文本字符串或消息段列表(OneBot 格式)
        """
        params = {
            "group_id": group_id,
            "message": message,
        }
        return await self._send_impl("send_group_msg", params)

    async def send_private_msg(
        self,
        user_id: int,
        message: str | list,
        auto_escape: bool = False,
    ) -> Optional[dict]:
        """发送私聊消息

        Args:
            user_id: 目标用户 QQ 号
            message: 文本字符串或消息段列表
            auto_escape: 为 True 时将 message 作为纯文本发送，不解析 CQ 码
        """
        params: dict = {
            "user_id": user_id,
            "message": message,
        }
        if auto_escape:
            params["auto_escape"] = True
        return await self._send_impl("send_private_msg", params)

    async def send_group_reply_msg(
        self,
        group_id: int,
        message: str,
        reply_message_id: int,
    ) -> Optional[dict]:
        """发送群聊回复消息

        Args:
            group_id: 目标群号
            message: 回复文本
            reply_message_id: 被回复的消息 ID
        """
        params = [
            {"type": "reply", "data": {"id": reply_message_id}},
            {"type": "text", "data": {"text": message}},
        ]
        return await self.send_group_msg(group_id, params)

    async def close(self) -> None:
        """关闭发送客户端，释放 HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self.log.debug("HTTP session 已关闭")

    async def send_group(self, message: GroupMessage) -> dict | None:
        """专门发送群聊消息对象

        Args:
            message: GroupMessage 消息体

        Returns:
            API 响应字典
        """
        return await self.async_send("send_group_msg", message.to_dict())

    async def send_private(self, message: PrivateMessage) -> dict | None:
        """专门发送私聊消息对象

        Args:
            message: PrivateMessage 消息体

        Returns:
            API 响应字典
        """
        return await self.async_send("send_private_msg", message.to_dict())

    async def send_group_poke(self, group_id: int, user_id: int) -> dict | None:
        """发送群戳一戳

        Args:
            group_id: 群号
            user_id: 目标用户 QQ
        """
        return await self.async_send("group_poke", {"group_id": group_id, "user_id": user_id})

    async def send_group_json(self, group_id: int, json_dict: dict) -> dict | None:
        """发送群 JSON 卡片消息

        Args:
            group_id: 群号
            json_dict: JSON 数据字典
        """
        return await self.send_group_msg(group_id, [{"type": "json", "data": json_dict}])

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
        """分享音乐到群

        Args:
            group_id: 群号
            type: 音乐平台 (qq/163/kugou/kuwo/migu/custom)
            id: 音乐 ID(非 custom 时必填)
            url: 音乐链接(custom 时必填)
            image: 封面图片(custom 时必填)
            singer: 歌手(可选)
            title: 标题(可选)
            content: 内容描述(可选)
        """
        if type != "custom" and not id:
            raise ValueError("当 type 不是 'custom' 时,id 必须提供")
        if type == "custom" and (not url or not image):
            raise ValueError("当 type 是 'custom' 时,url 和 image 必须提供")

        data = {
            "type": type,
            "id": id,
            "url": url,
            "image": image,
            "singer": singer,
            "title": title,
            "content": content,
        }
        message = [{"type": "music", "data": {k: v for k, v in data.items() if v is not None}}]
        return await self.send_group_msg(group_id, message)

    async def set_group_ban(
        self,
        group_id: int | str,
        user_id: int | str,
        duration: int = 1800,
    ) -> dict | None:
        """禁言群成员

        Args:
            group_id: 群号
            user_id: 要禁言的成员 QQ 号
            duration: 禁言时长(秒)

        Returns:
            执行结果
        """
        return await self.async_send(
            "set_group_ban",
            {"group_id": group_id, "user_id": user_id, "duration": duration},
        )

    async def set_group_add_request(
        self,
        flag: str,
        approve: bool,
        reason: str = "不行哦!",
    ) -> dict | None:
        """处理加群请求

        Args:
            flag: 请求 ID
            approve: 是否同意
            reason: 拒绝理由(可选)
        """
        payload: dict = {"flag": flag, "approve": approve}
        if not approve:
            payload["reason"] = reason
        return await self.async_send("set_group_add_request", payload)

    async def delete_msg(
        self,
        message_id: int | str,
    ) -> dict | None:
        """撤回消息

        Args:
            message_id: 消息 ID

        Returns:
            执行结果
        """
        return await self.async_send("delete_msg", {"message_id": message_id})

    async def set_msg_emoji_like(
        self,
        message_id: int | str,
        emoji_id: int,
        set: bool = True,
    ) -> dict | None:
        """给消息贴表情

        Args:
            message_id: 消息 ID
            emoji_id: 表情 ID
            set: 是否贴(True=贴,False=取消)

        Returns:
            执行结果
        """
        return await self.async_send(
            "set_msg_emoji_like",
            {"message_id": message_id, "emoji_id": emoji_id, "set": set},
        )

    async def get_group_info(self, group_id: int) -> dict | None:
        """获取群信息"""
        return await self.async_send("get_group_info", {"group_id": group_id})

    async def get_stranger_info(self, qq_id: int | str) -> dict | None:
        """获取账号信息

        Args:
            qq_id: QQ 号

        Returns:
            账号信息字典
        """
        return await self.async_send("get_stranger_info", {"user_id": qq_id})

    async def get_msg_details(self, message_id: int | str) -> OneBotMessageEvent | None:
        """获取消息详情"""
        try:
            resp = await self.async_send("get_msg", {"message_id": message_id})
            data:dict = (resp or {}).get("data")
        except Exception as e:
            self.log.warning("获取消息详情失败 (message_id=%s): %s", message_id, e)
            return None
        try:
            if data.get("post_type"):
                data["post_type"] = "message"
                data.setdefault("self_id", 0)
                
            return OneBotMessageEvent(
                event=OneBotEvent.from_dict(data),
                send_client=self,
            )
        except Exception as e:
            self.log.warning("解析消息详情失败 (message_id=%s): %s", message_id, e)
            return None
        
    async def get_img_details(
        self,
        file: str | None = None,
        file_id: str | None = None,
    ) -> ImageDetails | None:
        """获取图片信息及路径

        通过文件路径、URL、Base64 或文件 ID 获取图片的详细信息。
        至少提供 ``file`` 或 ``file_id`` 其中之一。

        Args:
            file: 文件路径、URL 或 Base64 编码
            file_id: 文件 ID

        Returns:
            ImageDetails 字典，包含 file / url / file_size / file_name / base64 五个字段。
        """
        params: dict = {}
        if file is not None:
            params["file"] = file
        if file_id is not None:
            params["file_id"] = file_id
        resp = await self.async_send("get_image", params)
        if resp and resp.get("status") == "ok":
            return resp.get("data")
        return None

    async def get_recordg_details(
        self,
        file: str,
        file_id: str,
        out_format: str = "mp3",
    ) -> dict | None:
        """获取语音消息详情

        Args:
            file: 文件路径
            file_id: 文件 ID
            out_format: 输出格式(mp3/amr/wma/m4a/spx/ogg/wav/flac)
        """
        return await self.async_send(
            "get_recordg",
            {"file": file, "file_id": file_id, "out_format": out_format},
        )


    async def _resolve_file_url(
        self,
        url: str,
        default: bool = False,
        local_Path_type: bool = True,
        base_dir: str = "img",
    ) -> str:
        """解析文件 URL,支持默认路径和本地文件协议

        Args:
            url: 原始 URL 或文件名
            default: 是否使用默认目录拼接
            local_Path_type: 是否添加 file:// 前缀
            base_dir: 默认目录名(img/audio/video/file)

        Returns:
            解析后的 URL 字符串
        """
        if default and self.file_paths:
            base = getattr(self.file_paths, base_dir, None)
            if base:
                url = str(base / url)
        if local_Path_type and not url.startswith(("http://", "https://", "base64://")):
            url = f"file://{url}"
        return url

    async def send_group_pictures(
        self,
        group_id: int,
        url_img: str = "img_ATRI.png",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送群图片

        Args:
            group_id: 群号
            url_img: 图片 URL 或文件名
            default: 是否使用默认图片目录
            local_Path_type: 是否按本地文件处理
        """
        file_url = await self._resolve_file_url(url_img, default, local_Path_type, base_dir="img")
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": file_url}}],
            },
        )

    async def send_group_image(
        self,
        group_id: int,
        url_img: str,
    ) -> Optional[dict]:
        """发送群聊图片

        Args:
            group_id: 群号
            url_img: 图片 URL

        完整功能请使用 send_group_pictures
        """
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": url_img}}],
            },
        )

    async def send_group_video(
        self,
        group_id: int,
        url_video: str = "ATRIの珍贵录像.mp4",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送群视频

        Args:
            group_id: 群号
            url_video: 视频 URL 或文件名
            default: 是否使用默认视频目录
            local_Path_type: 是否按本地文件处理
        """
        file_url = await self._resolve_file_url(url_video, default, local_Path_type, base_dir="video")
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "video", "data": {"file": file_url}}],
            },
        )

    async def send_group_audio(
        self,
        group_id: int,
        url_audio: str = "Atri my dear moments.mp3",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        """发送群聊语音(增强版，支持默认路径和本地文件协议)

        Args:
            group_id: 群号
            url_audio: 语音 URL 或文件名
            default: 是否使用默认音频目录
            local_Path_type: 是否按本地文件处理
        """
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
        url_file: str = "ATRI的文件.txt",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        """发送群文件(增强版，支持默认路径和本地文件协议)

        Args:
            group_id: 群号
            url_file: 文件 URL 或文件名
            name: 自定义文件名
            default: 是否使用默认文件目录
            local_Path_type: 是否按本地文件处理
        """
        raw_path = url_file
        if default and self.file_paths:
            raw_path = str(self.file_paths.file / url_file)
        data: dict = {"file": f"file://{raw_path}" if local_Path_type else raw_path}
        if name:
            data["name"] = name
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "file", "data": data}],
            },
        )

    async def send_personal_pictures(
        self,
        qq_id: int,
        url_img: str = "img_ATRI.png",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> dict | None:
        """发送私聊图片

        Args:
            qq_id: 目标 QQ 号
            url_img: 图片 URL 或文件名
            default: 是否使用默认图片目录
            local_Path_type: 是否按本地文件处理
        """
        file_url = await self._resolve_file_url(url_img, default, local_Path_type, base_dir="img")
        message = [{"type": "image", "data": {"file": file_url}}]
        return await self.send_private_msg(qq_id, message)

    async def send_personal_audio(
        self,
        qq_id: int,
        url_audio: str = "Atri my dear moments.mp3",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> dict | None:
        """发送私聊语音

        Args:
            qq_id: 目标 QQ 号
            url_audio: 语音 URL 或文件名
            default: 是否使用默认音频目录
            local_Path_type: 是否按本地文件处理
        """
        file_url = await self._resolve_file_url(url_audio, default, local_Path_type, base_dir="audio")
        message = [{"type": "record", "data": {"file": file_url}}]
        return await self.send_private_msg(qq_id, message)

    async def send_personal_file(
        self,
        qq_id: int,
        url_file: str = "ATRI的文件.txt",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送私聊文件

        Args:
            qq_id: 目标 QQ 号
            url_file: 文件 URL 或文件名
            name: 自定义文件名
            default: 是否使用默认文件目录
            local_Path_type: 是否按本地文件处理
        """
        raw_path = url_file
        if default and self.file_paths:
            raw_path = str(self.file_paths.file / url_file)

        data_payload: dict = {
            "file": f"file://{raw_path}" if local_Path_type else raw_path,
        }
        if name:
            data_payload["name"] = name

        message = [{"type": "file", "data": data_payload}]
        return await self.send_private_msg(qq_id, message)

    def __getattr__(self, item: str):
        """动态代理：将未定义的方法调用转换为 API 请求
        
        例如 client.some_api(param=value) 等价于 client.async_send("some_api", {"param": value})
        """
        if item in ("cleanup", "initialize") or item.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

        async def _dynamic_api_call(**kwargs) -> dict | None:
            return await self.async_send(url=item, payload={k: v for k, v in kwargs.items() if v is not None})

        return _dynamic_api_call

    async def send_group_merge_text(
        self,
        group_id: int,
        message: str,
        source: str = "男娘秘籍",
        preview: str = "ATRI:晚上一个人偷偷看[图片]",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> Optional[dict]:
        """发送群合并转发消息(单文本)

        将单条文本包装为合并转发消息发送，用于防止长消息刷屏。

        Args:
            group_id: 群号
            message: 消息内容
            source: 消息来源标题
            preview: 预览文本
            user_id: 发送者 QQ(用于合并转发节点)
            nickname: 发送者昵称

        Returns:
            API 响应
        """
        payload = {
            "group_id": group_id,
            "messages": [
                {
                    "type": "node",
                    "data": {
                        "user_id": str(user_id),
                        "nickname": nickname,
                        "content": [
                            {"type": "text", "data": {"text": message}}
                        ],
                    },
                }
            ],
            "news": [{"text": preview}],
            "prompt": "果然是群聊天记录",
            "summary": "点击即看",
            "source": source,
        }
        return await self._send_impl("send_group_forward_msg", payload)

    async def send_group_merge_forward(
        self,
        group_id: int,
        input_messages: list[list[dict]],
        source: str = "男娘秘籍",
        preview: str = "ATRI:晚上一个人偷偷看[图片]",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> Optional[dict]:
        """发送群合并转发消息(多节点)

        Args:
            group_id: 群号
            input_messages: 多条消息内容，每条为 OneBot 消息段列表
            source: 消息来源标题
            preview: 预览文本
            user_id: 发送者 QQ(用于合并转发节点)
            nickname: 发送者昵称

        Returns:
            API 响应
        """
        messages = []
        for msg in input_messages:
            messages.append(
                {
                    "type": "node",
                    "data": {
                        "user_id": str(user_id),
                        "nickname": nickname,
                        "content": msg,
                    },
                }
            )
        payload = {
            "group_id": group_id,
            "messages": messages,
            "news": [{"text": preview}],
            "prompt": "果然是群聊天记录",
            "summary": "点击即看",
            "source": source,
        }
        return await self._send_impl("send_group_forward_msg", payload)
