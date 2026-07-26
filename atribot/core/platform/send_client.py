from abc import ABC, abstractmethod
from typing import Any, Optional

from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage


class SendClientBase(ABC):
    """发送客户端基类 —— 所有平台发消息的底座

    核心方法（@abstractmethod,子类必须实现）:
        - send() — 发送已构建的 SendMessage 对象
        - async_send() — 通用 API 调用
        - send_group_msg() — 发送群聊消息
        - send_private_msg() — 发送私聊消息
        - close() — 清理资源

    快捷方法（有默认实现，子类可覆写优化）:
        - send_group() / send_private() — 类型化消息快捷发送
        - send_group_reply_msg() — 群聊回复

    平台操作（默认抛出 NotImplementedError,子类按需覆写:
        - 群管理: set_group_ban, set_group_add_request, delete_msg
        - 互动: send_group_poke, set_msg_emoji_like
        - 富媒体: send_group_json, send_group_music, send_group_pictures,
                 send_group_image, send_group_video, send_group_audio, send_group_file
        - 私聊媒体: send_personal_pictures, send_personal_audio
        - 查询: get_group_info, get_stranger_info, get_msg_details,
               get_img_details, get_recordg_details
    """

    @abstractmethod
    async def send(self, message: SendMessage) -> Optional[dict]:
        """发送已构建好的消息对象

        Args:
            message: GroupMessage 或 PrivateMessage 实例

        Returns:
            API 响应字典，或 None
        """
        ...

    @abstractmethod
    async def async_send(self, action: str, params: dict) -> Optional[dict]:
        """通用的发送请求

        Args:
            action: API 动作名称（如 "send_group_msg"
            params: 请求参数字典

        Returns:
            API 响应字典，或 None
        """
        ...

    @abstractmethod
    async def send_group_msg(
        self,
        group_id: int,
        message: str | list,
    ) -> Optional[dict]:
        """发送群聊消息

        Args:
            group_id: 目标群号
            message: 文本字符串或消息段列表
        """
        ...

    @abstractmethod
    async def send_private_msg(
        self,
        user_id: int,
        message: str | list,
        auto_escape: bool = False,
    ) -> Optional[dict]:
        """发送私聊消息

        Args:
            user_id: 目标用户 ID
            message: 文本字符串或消息段列表
            auto_escape: 为 True 时将 message 作为纯文本发送，不解析 CQ 码
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭发送客户端，释放资源"""
        ...

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

        默认实现使用 send_group_msg 拼接 reply 段，子类可覆写优化。
        """
        params = [
            {"type": "reply", "data": {"id": reply_message_id}},
            {"type": "text", "data": {"text": message}},
        ]
        return await self.send_group_msg(group_id, params)

    async def send_group_poke(self, group_id: int, user_id: int) -> dict | None:
        """发送群戳一戳"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_poke")

    async def send_group_json(self, group_id: int, json_dict: dict) -> dict | None:
        """发送群 JSON 卡片消息"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_json")

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
        """分享音乐到群"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_music")

    async def set_group_ban(
        self,
        group_id: int | str,
        user_id: int | str,
        duration: int = 1800,
    ) -> dict | None:
        """禁言群成员

        Args:
            group_id: 群号
            user_id: 要禁言的成员 ID
            duration: 禁言时长(秒)
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_group_ban")

    async def set_group_add_request(
        self,
        flag: str,
        approve: bool,
        reason: str = "",
    ) -> dict | None:
        """处理加群请求

        Args:
            flag: 请求 ID
            approve: 是否同意
            reason: 拒绝理由(可选)
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_group_add_request")

    async def delete_msg(
        self,
        message_id: int | str,
    ) -> dict | None:
        """撤回消息

        Args:
            message_id: 消息 ID
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 delete_msg")

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
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_msg_emoji_like")

    async def send_group_pictures(
        self,
        group_id: int,
        url_img: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送群图片"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_pictures")

    async def send_group_image(
        self,
        group_id: int,
        url_img: str,
    ) -> Optional[dict]:
        """发送群聊图片（简易版）"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_image")

    async def send_group_video(
        self,
        group_id: int,
        url_video: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送群视频"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_video")

    async def send_group_audio(
        self,
        group_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        """发送群聊语音"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_audio")

    async def send_group_file(
        self,
        group_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> Optional[dict]:
        """发送群文件"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_file")

    async def send_personal_pictures(
        self,
        qq_id: int,
        url_img: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> dict | None:
        """发送私聊图片"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_personal_pictures")

    async def send_personal_audio(
        self,
        qq_id: int,
        url_audio: str = "",
        default: bool = False,
        local_Path_type: bool = False,
    ) -> dict | None:
        """发送私聊语音"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_personal_audio")

    async def get_group_info(self, group_id: int) -> dict | None:
        """获取群信息"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_group_info")

    async def get_stranger_info(self, qq_id: int | str) -> dict | None:
        """获取用户信息

        Args:
            qq_id: 用户 ID
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_stranger_info")

    async def get_msg_details(self, message_id: int | str) -> Any | None:
        """获取消息详情

        Args:
            message_id: 消息 ID

        Returns:
            平台消息事件对象（如 OneBotMessageEvent),或 None
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_msg_details")

    async def get_img_details(self, file_id: str) -> dict | None:
        """获取图片消息详情"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_img_details")

    async def get_recordg_details(
        self,
        file: str,
        file_id: str,
        out_format: str = "mp3",
    ) -> dict | None:
        """获取语音消息详情"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_recordg_details")

    async def send_group_merge_text(
        self,
        group_id: int,
        message: str,
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        """发送群合并转发消息(单文本)

        Args:
            group_id: 群号
            message: 消息内容
            source: 消息来源标题
            preview: 预览文本
            user_id: 发送者 QQ
            nickname: 发送者昵称
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_merge_text")

    async def send_group_merge_forward(
        self,
        group_id: int,
        input_messages: list[list[dict]],
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        """发送群合并转发消息(多节点)

        Args:
            group_id: 群号
            input_messages: 多条消息内容，每条为 OneBot 消息段列表
            source: 消息来源标题
            preview: 预览文本
            user_id: 发送者 QQ
            nickname: 发送者昵称
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_merge_forward")
