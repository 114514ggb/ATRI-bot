from typing import Any

from atribot.core.platform.onebot.send import OneBotSendClient
from atribot.core.platform.send_client import LoginInfo
from atribot.core.platform.snowluma.message_event import SnowLumaMessageEvent
from atribot.core.type.onebot_event_types import OneBotEvent


class SnowLumaSendClient(OneBotSendClient):
    """SnowLuma 发送客户端

    SnowLuma 实现了 OneBot v11 动作集（含 NapCat 兼容形状），
    仅需覆盖与 NapCat 不一致的少部分动作与响应处理。
    """

    async def get_login_info(self) -> LoginInfo | None:
        """获取当前登录帐号的信息

        SnowLuma 的 get_login_info 返回标准 OneBot 响应，
        data 中仅保证 user_id / nickname 两个字段。

        Returns:
            LoginInfo 字典；响应缺少 data.user_id 时返回 None。
        """
        try:
            resp = await self.async_send("get_login_info", {})
        except Exception as e:
            self.log.warning("获取登录账号信息失败: %s", e)
            return None

        data: Any = resp.get("data") if isinstance(resp, dict) else None
        if isinstance(resp, dict) and resp.get("status") not in (None, "ok"):
            self.log.warning("获取登录账号信息失败: %s", resp)
            return None
        if not isinstance(data, dict) or data.get("user_id") is None:
            self.log.warning("获取登录账号信息失败: %s", resp)
            return None

        try:
            return LoginInfo(
                user_id=int(data["user_id"]),
                nickname=str(data.get("nickname") or ""),
            )
        except (TypeError, ValueError) as e:
            self.log.warning("解析登录账号信息失败: %s (%s)", e, data)
            return None

    async def get_recordg_details(
        self,
        file: str,
        file_id: str,
        out_format: str = "mp3",
    ) -> dict | None:
        """获取语音消息详情（SnowLuma 的动作名为 get_record）"""
        return await self.async_send(
            "get_record",
            {"file": file, "file_id": file_id, "out_format": out_format},
        )

    async def get_msg_details(self, message_id: int | str) -> SnowLumaMessageEvent | None:
        """获取消息详情

        SnowLuma 的 get_msg 返回标准 OneBot 消息对象，可能不含 post_type，
        需要补齐后再解析为事件。
        """
        try:
            resp = await self.async_send("get_msg", {"message_id": message_id})
            data: Any = (resp or {}).get("data")
        except Exception as e:
            self.log.warning("获取消息详情失败 (message_id=%s): %s", message_id, e)
            return None

        if not isinstance(data, dict):
            self.log.warning("获取消息详情失败 (message_id=%s): 响应缺少 data", message_id)
            return None

        normalized = dict(data)
        normalized.setdefault("post_type", "message")
        normalized.setdefault("self_id", 0)
        normalized.setdefault("message_id", message_id)
        if not normalized.get("message_type"):
            normalized["message_type"] = "group" if normalized.get("group_id") else "private"

        try:
            return SnowLumaMessageEvent(
                event=OneBotEvent.from_dict(normalized),
                send_client=self,
            )
        except Exception as e:
            self.log.warning("解析消息详情失败 (message_id=%s): %s", message_id, e)
            return None
