import logging
from typing import Literal, Optional

import aiohttp

from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage


class OneBotSendClient:
    """OneBot 消息发送客户端"""

    def __init__(
        self,
        access_token: str = "ATRI",
        http_base_url: str = "http://localhost:8080",
        connection_type: Literal["http", "WebSocket_client", "WebSocket_server"] = "http",
        ws_connection=None,  # OneBotWSClient | OneBotWSServer
        log: logging.Logger | None = None,
    ):
        self.access_token = access_token
        self.http_base_url = http_base_url
        self.connection_type = connection_type
        self._ws = ws_connection
        self.log = log or logging.getLogger("OneBotSendClient")

        self._http_session: Optional[aiohttp.ClientSession] = None
        if connection_type == "http":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }
            self._http_session = aiohttp.ClientSession(headers=headers)
            self._send_impl = self._send_http
        elif connection_type != "http":
            self._send_impl = self._send_ws
        else:
            raise ValueError(f"不支持的连接类型: {connection_type}")

        self.log.info("发送客户端已就绪 (模式: %s)", connection_type)

    async def _send_http(self, action: str, params: dict, echo: bool = False) -> Optional[dict]:
        """通过 HTTP POST 发送"""
        if not self._http_session:
            raise RuntimeError("HTTP session 未初始化")
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

    async def _send_ws(self, action: str, params: dict, echo: bool = False) -> Optional[dict]:
        """通过 WebSocket 发送"""
        if not self._ws:
            raise RuntimeError("WebSocket 连接未就绪")

        message = {
            "action": action,
            "params": params,
        }
        try:
            return await self._ws.send(message, with_echo=echo)
        except Exception as e:
            self.log.error("WS 发送失败: %s", e)
            return None

    async def send(self, message: SendMessage, echo: bool = False) -> Optional[dict]:
        """发送消息对象

        Args:
            message: GroupMessage 或 PrivateMessage 实例
            echo: 是否等待返回结果

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

        return await self._send_impl(action, message.to_dict(), echo=echo)

    async def send_group_msg(
        self,
        group_id: int,
        message: str | list,
    ) -> Optional[dict]:
        """发送群聊消息（便捷方法）

        Args:
            group_id: 目标群号
            message: 文本字符串或消息段列表（OneBot 格式）
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
    ) -> Optional[dict]:
        """发送私聊消息（便捷方法）

        Args:
            user_id: 目标用户 QQ 号
            message: 文本字符串或消息段列表（OneBot 格式）
        """
        params = {
            "user_id": user_id,
            "message": message,
        }
        return await self._send_impl("send_private_msg", params)

    async def send_group_reply_msg(
        self,
        group_id: int,
        message: str,
        reply_message_id: int,
    ) -> Optional[dict]:
        """发送群聊回复消息"""
        params = [
            {"type": "reply", "data": {"id": reply_message_id}},
            {"type": "text", "data": {"text": message}},
        ]
        return await self.send_group_msg(group_id, params)

    async def send_group_audio(
        self,
        group_id: int,
        url_audio: str,
    ) -> Optional[dict]:
        """发送群聊语音"""
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "record", "data": {"file": url_audio}}],
            },
        )

    async def send_group_image(
        self,
        group_id: int,
        url_img: str,
    ) -> Optional[dict]:
        """发送群聊图片"""
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": url_img}}],
            },
        )

    async def send_group_file(
        self,
        group_id: int,
        url_file: str,
        name: str | None = None,
    ) -> Optional[dict]:
        """发送群文件"""
        data: dict = {"file": url_file}
        if name:
            data["name"] = name
        return await self._send_impl(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": [{"type": "file", "data": data}],
            },
        )

    async def close(self) -> None:
        """关闭发送客户端，释放 HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self.log.debug("HTTP session 已关闭")
