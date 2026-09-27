from abc import ABC, abstractmethod
from typing import Optional, TypedDict

from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.core.type.chat_message_types import GroupMessage, PrivateMessage, SendMessage


class ImageDetails(TypedDict):
    """get_image API 返回的图片信息"""

    file: str
    """图片在 NapCat 服务器的本地路径"""
    url: str
    """图片下载 URL"""
    file_size: str
    """图片大小（字节，字符串形式）"""
    file_name: str
    """图片文件名"""
    base64: str
    """图片 Base64 编码（不含 data:image 前缀）"""


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
        - 私聊媒体: send_personal_pictures, send_personal_audio,
                   send_personal_file, send_personal_music
        - 查询: get_group_info, get_stranger_info, get_msg_details,
               get_img_details, get_recordg_details
        - 群扩展: set_group_admin, set_group_special_title, send_group_sign,
                 upload_image_to_qun_album, set_essence_msg, delete_essence_msg,
                 get_group_info_ex, get_group_list, get_group_member_list,
                 get_group_member_info, get_essence_msg_list
        - 账号/用户: set_qq_avatar, set_self_longnick, send_like,
                    set_input_status, set_friend_add_request
        - QQ空间: send_qzone_msg, delete_qzone_msg
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
            message: 文本字符串或消息段列表,发送到qq的话会解析cq码
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

    async def send_personal_file(
        self,
        qq_id: int,
        url_file: str = "",
        name: str | None = None,
        default: bool = False,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发送私聊文件

        Args:
            qq_id: 目标用户 QQ 号
            url_file: 文件 URL、路径或 Base64
            name: 自定义文件名(可选)
            default: 是否使用默认文件目录
            local_Path_type: 是否按本地文件处理
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_personal_file")

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
    ) -> dict | None:
        """分享音乐到私聊

        Args:
            qq_id: 目标用户 QQ 号
            type: 音乐平台 (qq/163/kugou/kuwo/migu/custom)
            id: 音乐 ID(非 custom 时必填)
            url: 音乐链接(custom 时必填)
            image: 封面图片(custom 时必填)
            singer: 歌手(可选)
            title: 标题(可选)
            content: 内容描述(可选)
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_personal_music")

    async def get_group_info(self, group_id: int) -> dict | None:
        """获取群信息"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_group_info")

    async def get_stranger_info(self, qq_id: int | str) -> dict | None:
        """获取用户信息

        Args:
            qq_id: 用户 ID
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_stranger_info")

    async def get_msg_details(self, message_id: int | str) -> MessageEventEnvelope | None:
        """获取消息详情

        Args:
            message_id: 消息 ID

        Returns:
            平台消息事件对象（如 OneBotMessageEvent),或 None
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_msg_details")

    async def get_img_details(
        self,
        file: str | None = None,
        file_id: str | None = None,
    ) -> ImageDetails | None:
        """获取图片信息及路径

        通过文件路径、URL、Base64 或文件 ID 获取图片的详细信息。
        至少提供 ``file`` 或 ``file_id`` 其中之一。

        Args:
            file: 文件路径、URL 或 Base64 编码（如收到的图片消息段中的 ``file`` 字段）
            file_id: 文件 ID（如收到的图片消息段中的 ``file_id`` 字段）

        Returns:
            ImageDetails 字典，包含 file / url / file_size / file_name / base64 五个字段；
            若请求失败或图片不存在则返回 None。
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_img_details")

    async def get_recordg_details(
        self,
        file: str,
        file_id: str,
        out_format: str = "mp3",
    ) -> dict | None:
        """获取语音消息详情"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_recordg_details")

    async def set_group_admin(
        self,
        group_id: int | str,
        user_id: int | str,
        enable: bool = True,
    ) -> dict | None:
        """设置或取消群管理员

        Args:
            group_id (int | str): 群号
            user_id (int | str): 目标成员 QQ 号
            enable (bool): True=设为管理员，False=取消管理员。默认为 True

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_group_admin")

    async def set_group_special_title(
        self,
        group_id: int | str,
        user_id: int | str,
        special_title: str = "",
    ) -> dict | None:
        """设置群成员的专属头衔

        Args:
            group_id (int | str): 群号
            user_id (int | str): 目标成员 QQ 号
            special_title (str): 专属头衔内容，空字符串表示清除头衔。默认为空字符串

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_group_special_title")

    async def send_group_sign(self, group_id: int | str) -> dict | None:
        """群打卡（群签到）

        Args:
            group_id (int | str): 群号

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_group_sign")

    async def upload_image_to_qun_album(
        self,
        group_id: int | str,
        album_id: str,
        album_name: str,
        file: str,
        local_Path_type: bool = True,
    ) -> dict | None:
        """上传图片到群相册

        Args:
            group_id (int | str): 群号
            album_id (str): 相册 ID
            album_name (str): 相册名称
            file (str): 图片路径、URL 或 Base64，支持 ``file://`` / ``http(s)://`` / ``base64://``
            local_Path_type (bool): 是否将本地路径按 ``file://`` 协议处理。默认为 True

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 upload_image_to_qun_album")

    async def set_essence_msg(self, message_id: int | str) -> dict | None:
        """将一条消息设置为群精华消息

        Args:
            message_id (int | str): 消息 ID

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_essence_msg")

    async def delete_essence_msg(
        self,
        message_id: int | str,
        msg_seq: str | None = None,
        msg_random: str | None = None,
        group_id: int | str | None = None,
    ) -> dict | None:
        """将一条消息移出群精华消息列表

        Args:
            message_id (int | str): 消息 ID
            msg_seq (str | None): 消息序号，None=不提交该字段
            msg_random (str | None): 消息随机数，None=不提交该字段
            group_id (int | str | None): 群号，None=不提交该字段

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 delete_essence_msg")

    # ---------- 群扩展查询 ----------

    async def get_group_info_ex(self, group_id: int | str) -> dict | None:
        """获取群详细信息（扩展接口）

        Args:
            group_id (int | str): 群号

        Returns:
            dict | None: 解包后的 data 字段（群详细信息）；失败返回 None
                （子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_group_info_ex")

    async def get_group_list(self, no_cache: bool | None = None) -> list[dict] | None:
        """获取当前账号的群列表

        Args:
            no_cache (bool | None): 是否忽略缓存强制拉取，None=不提交该字段。默认为 None

        Returns:
            list[dict] | None: 解包后的 data 字段（群信息列表）；失败返回 None
                （子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_group_list")

    async def get_group_member_list(
        self,
        group_id: int | str,
        no_cache: bool | None = None,
    ) -> list[dict] | None:
        """获取群成员列表

        Args:
            group_id (int | str): 群号
            no_cache (bool | None): 是否忽略缓存强制拉取，None=不提交该字段。默认为 None

        Returns:
            list[dict] | None: 解包后的 data 字段（成员列表）；失败返回 None
                （子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_group_member_list")

    async def get_group_member_info(
        self,
        group_id: int | str,
        user_id: int | str,
        no_cache: bool | None = None,
    ) -> dict | None:
        """获取群成员信息

        Args:
            group_id (int | str): 群号
            user_id (int | str): 目标成员 QQ 号
            no_cache (bool | None): 是否忽略缓存强制拉取，None=不提交该字段。默认为 None

        Returns:
            dict | None: 解包后的 data 字段（成员信息）；失败返回 None
                （子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_group_member_info")

    async def get_essence_msg_list(self, group_id: int | str) -> list[dict] | None:
        """获取群精华消息列表

        Args:
            group_id (int | str): 群号

        Returns:
            list[dict] | None: 解包后的 data 字段（精华消息列表）；失败返回 None
                （子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 get_essence_msg_list")

    async def set_qq_avatar(self, file: str, local_Path_type: bool = True) -> dict | None:
        """修改当前账号的 QQ 头像

        Args:
            file (str): 图片路径、URL 或 Base64，支持 ``file://`` / ``http(s)://`` / ``base64://``
            local_Path_type (bool): 是否将本地路径按 ``file://`` 协议处理。默认为 True

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_qq_avatar")

    async def set_self_longnick(self, long_nick: str) -> dict | None:
        """修改当前登录账号的个性签名

        Args:
            long_nick (str): 新的签名内容

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_self_longnick")

    async def send_like(self, user_id: int | str, times: int | str = 1) -> dict | None:
        """给指定用户点赞

        Args:
            user_id (int | str): 对方 QQ 号
            times (int | str): 点赞次数。默认为 1

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_like")

    async def set_input_status(self, user_id: int | str, event_type: int) -> dict | None:
        """设置输入状态（对方侧显示“正在输入”等提示）

        Args:
            user_id (int | str): 目标用户 QQ 号
            event_type (int): 输入状态类型，取值由 NapCat 定义（如 1=正在输入），原样透传不校验

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_input_status")

    async def set_friend_add_request(
        self,
        flag: str,
        approve: bool = True,
        remark: str = "",
    ) -> dict | None:
        """处理加好友请求

        Args:
            flag (str): 加好友请求的 flag（从请求事件上报中获取）
            approve (bool): True=同意，False=拒绝。默认为 True
            remark (str): 添加后的好友备注，空字符串=不提交该字段。默认为空字符串

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 set_friend_add_request")

    async def send_qzone_msg(
        self,
        content: str,
        images: list[str] | None = None,
        ugc_right: int | str = 1,
        target_uins: list[int | str] | None = None,
        local_Path_type: bool = True,
    ) -> dict | None:
        """发表 QQ 空间说说

        Args:
            content (str): 说说正文
            images (list[str] | None): 配图列表，元素支持 ``file://`` / ``http(s)://`` /
                ``base64://``；None 或空列表=不提交该字段（纯文字说说）
            ugc_right (int | str): 查看权限。1=所有人可见，4=好友可见，16=部分好友可见，
                64=仅自己可见，128=部分好友不可见。默认为 1
            target_uins (list[int | str] | None): ugc_right 为 16/128 时权限作用的 QQ 号列表；
                None 或空列表=不提交该字段
            local_Path_type (bool): 是否将本地路径按 ``file://`` 协议处理。默认为 True

        Returns:
            dict | None: 原始 API 响应；成功时 ``data.tid`` 为说说 ID（可用于 delete_qzone_msg）
                （子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_qzone_msg")

    async def delete_qzone_msg(self, tid: str) -> dict | None:
        """删除 QQ 空间说说

        Args:
            tid (str): 说说 ID（来自 send_qzone_msg 或空间说说列表接口）

        Returns:
            dict | None: 原始 API 响应（子类未实现时抛出 NotImplementedError）
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 delete_qzone_msg")

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

    async def send_private_merge_text(
        self,
        qq_id: int,
        message: str,
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        """发送私聊合并转发消息(单文本)

        将单条文本包装为合并转发消息发送，用于防止长消息刷屏。

        Args:
            qq_id: 目标用户 QQ
            message: 消息内容
            source: 消息来源标题
            preview: 预览文本
            user_id: 发送者 QQ(用于合并转发节点)
            nickname: 发送者昵称
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_private_merge_text")

    async def send_private_merge_forward(
        self,
        qq_id: int,
        input_messages: list[list[dict]],
        source: str = "ATRI",
        preview: str = "ATRI:点击查看消息",
        user_id: int = 3889393615,
        nickname: str = "ATRI-亚托莉",
    ) -> dict | None:
        """发送私聊合并转发消息(多节点)

        Args:
            qq_id: 目标用户 QQ
            input_messages: 多条消息内容，每条为 OneBot 消息段列表
            source: 消息来源标题
            preview: 预览文本
            user_id: 发送者 QQ(用于合并转发节点)
            nickname: 发送者昵称
        """
        raise NotImplementedError(f"{type(self).__name__} 未实现 send_private_merge_forward")
