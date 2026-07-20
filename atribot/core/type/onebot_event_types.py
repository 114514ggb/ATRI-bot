import datetime
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from atribot.core.type.chat_message_types import (
    ChatMessage,
    MessageSegment,
    TextSegment,
    parse_onebot_segments,
)

TEXT_LENGTH_LIMIT = 2000


class PostType(str, Enum):
    """事件大类"""
    META = "meta_event"
    """元事件"""
    MESSAGE = "message"
    """消息事件"""
    MESSAGE_SENT = "message_sent"
    """自己消息发送事件"""
    NOTICE = "notice"
    """通知事件"""
    REQUEST = "request"
    """请求事件"""
    

class MetaEventType(str, Enum):
    """元事件子类型"""
    HEARTBEAT = "heartbeat"
    """心跳事件"""
    LIFECYCLE = "lifecycle"
    """生命周期事件"""


class LifeCycleSubType(str, Enum):
    """生命周期子类型"""
    ENABLE = "enable"
    """启用"""
    DISABLE = "disable"
    """禁用"""
    CONNECT = "connect"
    """连接"""


class NoticeType(str, Enum):
    """通知事件子类型"""
    FRIEND_ADD = "friend_add"
    """好友添加"""
    FRIEND_RECALL = "friend_recall"
    """好友消息撤回"""
    GROUP_RECALL = "group_recall"
    """群消息撤回"""
    GROUP_INCREASE = "group_increase"
    """群成员增加"""
    GROUP_DECREASE = "group_decrease"
    """群成员减少"""
    GROUP_ADMIN = "group_admin"
    """群管理员变动"""
    GROUP_BAN = "group_ban"
    """群禁言"""
    GROUP_UPLOAD = "group_upload"
    """群文件上传"""
    GROUP_CARD = "group_card"
    """群名片变更"""
    NOTIFY = "notify"
    """通用通知(子类型由 sub_type 区分)"""
    ESSENCE = "essence"
    """精华消息"""
    GROUP_MSG_EMOJI_LIKE = "group_msg_emoji_like"
    """表情回应"""
    BOT_OFFLINE = "bot_offline"
    """机器人离线"""


class NotifySubType(str, Enum):
    """notify 类通知的 sub_type 值"""
    POKE = "poke"
    """戳一戳"""
    PROFILE_LIKE = "profile_like"
    """资料点赞"""
    INPUT_STATUS = "input_status"
    """输入状态"""
    GROUP_NAME = "group_name"
    """群名变更"""
    TITLE = "title"
    """群头衔变更"""
    GRAY_TIP = "gray_tip"
    """群灰条消息"""


class GroupDecreaseSubType(str, Enum):
    """群成员减少子类型"""
    LEAVE = "leave"
    """主动退群"""
    KICK = "kick"
    """被踢"""
    KICK_ME = "kick_me"
    """我被踢"""
    DISBAND = "disband"
    """群解散"""


class GroupIncreaseSubType(str, Enum):
    """群成员增加子类型"""
    APPROVE = "approve"
    """同意加群"""
    INVITE = "invite"
    """邀请加群"""


class GroupAdminSubType(str, Enum):
    """群管理员变动子类型"""
    SET = "set"
    """设置管理员"""
    UNSET = "unset"
    """取消管理员"""


class GroupBanSubType(str, Enum):
    """群禁言子类型"""
    BAN = "ban"
    """禁言"""
    LIFT_BAN = "lift_ban"
    """解除禁言"""


class EssenceSubType(str, Enum):
    """精华消息子类型"""
    ADD = "add"
    """添加精华"""
    DELETE = "delete"
    """删除精华"""


class MessageType(str, Enum):
    """消息类型(message_type)"""
    PRIVATE = "private"
    """私聊消息"""
    GROUP = "group"
    """群聊消息"""


class PrivateSubType(str, Enum):
    """私聊消息子类型"""
    FRIEND = "friend"
    """好友"""
    GROUP = "group"
    """群临时会话"""
    OTHER = "other"
    """其他"""


class SenderRole(str, Enum):
    """群成员角色"""
    OWNER = "owner"
    """群主"""
    ADMIN = "admin"
    """管理员"""
    MEMBER = "member"
    """普通成员"""


class SenderSex(str, Enum):
    """性别"""
    MALE = "male"
    """男"""
    FEMALE = "female"
    """女"""
    UNKNOWN = "unknown"
    """未知"""


class RequestType(str, Enum):
    """请求事件子类型"""
    FRIEND = "friend"
    """好友请求"""
    GROUP = "group"
    """群请求"""


@dataclass(slots=True)
class OneBotEvent(ABC):
    """所有 OneBot 事件的抽象基类

    定义了所有事件的共有字段，并提供 from_dict() 工厂方法自动分发到正确的子类
    """
    time: int
    """事件发生的时间戳(Unix 秒)"""
    self_id: int
    """机器人自身 QQ 号"""
    post_type: PostType
    """事件大类"""
    primeval: Dict[str, Any] = field(repr=False, default_factory=dict)
    """原始事件 JSON 字典"""

    _cached_simple: str = field(default="", init=False, repr=False)
    _cached_detailed: str = field(default="", init=False, repr=False)

    def _fmt_time(self) -> str:
        """将 Unix 时间戳格式化为 'YYYY-MM-DD HH:MM:SS'"""
        return datetime.datetime.fromtimestamp(self.time).strftime("%Y-%m-%d %H:%M:%S")

    @abstractmethod
    def _format_event_simple(self) -> str:
        """返回简洁中文描述"""
        ...

    @abstractmethod
    def _format_event_detailed(self) -> str:
        """返回详细 XML 格式化文本"""
        ...

    def format_event_simple(self) -> str:
        """获取简洁 AI 可读事件描述"""
        if not self._cached_simple:
            self._cached_simple = self._format_event_simple()
        return self._cached_simple

    @property
    def llm_formatted_message(self) -> str:
        """获取详细 AI 可读事件描述"""
        if not self._cached_detailed:
            self._cached_detailed = self._format_event_detailed()
        return self._cached_detailed

    def __str__(self) -> str:
        return self.format_event_simple()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OneBotEvent:
        """从 OneBot 原始 JSON 字典解析为对应的事件类型实例
        
        Args:
            data: 推送的原始事件 JSON 字典

        Returns:
            对应事件类型的实例

        Raises:
            ValueError: 无法识别的事件类型
        """
        post_type_str = data.get("post_type", "")
        try:
            post_type = PostType(post_type_str)
        except ValueError:
            raise ValueError(f"未知的 post_type: {post_type_str!r}") from None

        if post_type == PostType.NOTICE:
            return cls._parse_notice(data)
        elif post_type == PostType.MESSAGE:
            return cls._parse_message(data)
        elif post_type == PostType.META:
            return cls._parse_meta(data)
        elif post_type == PostType.MESSAGE_SENT:
            return cls._parse_message_sent(data)
        elif post_type == PostType.REQUEST:
            return cls._parse_request(data)
        else:
            raise ValueError(f"未处理的 post_type: {post_type}")

    @classmethod
    def _parse_meta(cls, data: Dict[str, Any]) -> OneBotEvent:
        meta_type = data.get("meta_event_type", "")
        if meta_type == MetaEventType.HEARTBEAT:
            return HeartbeatEvent.from_data(data)
        elif meta_type == MetaEventType.LIFECYCLE:
            return LifeCycleEvent.from_data(data)
        else:
            #未知元事件
            return MetaEvent.from_data(data)

    @classmethod
    def _parse_message(cls, data: Dict[str, Any]) -> OneBotEvent:
        message_type = data.get("message_type", "")
        if message_type == MessageType.GROUP:
            return GroupMessageEvent.from_data(data)
        elif message_type == MessageType.PRIVATE:
            return PrivateMessageEvent.from_data(data)
        else:
            return MessageEvent.from_data(data)

    @classmethod
    def _parse_message_sent(cls, data: Dict[str, Any]) -> OneBotEvent:
        return MessageSentEvent.from_data(data)

    @classmethod
    def _parse_notice(cls, data: Dict[str, Any]) -> OneBotEvent:
        notice_type = data.get("notice_type", "")
        sub_type = data.get("sub_type", "")

        #群通知基类路由
        if notice_type == NoticeType.GROUP_INCREASE:
            return GroupIncreaseEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_MSG_EMOJI_LIKE:
            return GroupMsgEmojiLikeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_UPLOAD:
            return GroupUploadNoticeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_DECREASE:
            return GroupDecreaseEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_RECALL:
            return GroupRecallNoticeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_ADMIN:
            return GroupAdminNoticeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_BAN:
            return GroupBanEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_CARD:
            return GroupCardEvent.from_data(data)
        elif notice_type == NoticeType.ESSENCE:
            return GroupEssenceEvent.from_data(data)

        #notify
        elif notice_type == NoticeType.NOTIFY:
            if sub_type == NotifySubType.POKE:
                return PokeEvent.from_data(data)
            elif sub_type == NotifySubType.PROFILE_LIKE:
                return ProfileLikeEvent.from_data(data)
            elif sub_type == NotifySubType.INPUT_STATUS:
                return InputStatusEvent.from_data(data)
            elif sub_type == NotifySubType.GROUP_NAME:
                return GroupNameEvent.from_data(data)
            elif sub_type == NotifySubType.TITLE:
                return GroupTitleEvent.from_data(data)
            elif sub_type == NotifySubType.GRAY_TIP:
                return GroupGrayTipEvent.from_data(data)
            else:
                return NoticeEvent.from_data(data)

        #好友通知
        elif notice_type == NoticeType.FRIEND_RECALL:
            return FriendRecallNoticeEvent.from_data(data)
        elif notice_type == NoticeType.FRIEND_ADD:
            return FriendAddNoticeEvent.from_data(data)

        #bot离线
        elif notice_type == NoticeType.BOT_OFFLINE:
            return BotOfflineEvent.from_data(data)

        else:
            return NoticeEvent.from_data(data)

    @classmethod
    def _parse_request(cls, data: Dict[str, Any]) -> OneBotEvent:
        request_type = data.get("request_type", "")
        if request_type == RequestType.FRIEND:
            return FriendRequestEvent.from_data(data)
        elif request_type == RequestType.GROUP:
            return GroupRequestEvent.from_data(data)
        else:
            return RequestEvent.from_data(data)


@dataclass(slots=True)
class MetaEvent(OneBotEvent):
    """元事件基类

    与 OneBot 协议实现相关的事件，如心跳、生命周期等
    """
    meta_event_type: str = ""
    """元事件类型"""

    post_type: PostType = field(default=PostType.META, init=False)
    """事件大类(固定为元事件)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> MetaEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            meta_event_type=data.get("meta_event_type", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[元事件] {self.meta_event_type}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>meta</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<meta_event_type>{self.meta_event_type}</meta_event_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class HeartbeatEvent(MetaEvent):
    """心跳事件

    NapCat 定期发送，用于确认连接状态
    """
    status: Dict[str, Any] = field(default_factory=dict)
    """状态信息 {"online": bool, "good": bool}"""
    interval: int = 0
    """心跳间隔(毫秒)"""

    meta_event_type: str = field(default=MetaEventType.HEARTBEAT, init=False)
    """元事件类型(固定为心跳)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> HeartbeatEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            status=data.get("status", {}),
            interval=data.get("interval", 0),
            primeval=data,
        )

    @property
    def is_online(self) -> Optional[bool]:
        """机器人是否在线(可能为 None)"""
        return self.status.get("online")

    @property
    def is_good(self) -> bool:
        """状态是否良好"""
        return self.status.get("good", False)

    def _format_event_simple(self) -> str:
        return f"[心跳] 在线:{self.is_online} 状态良好:{self.is_good} 间隔:{self.interval}ms"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>heartbeat</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<status_online>{self.is_online}</status_online>"
            f"<status_good>{self.is_good}</status_good>"
            f"<interval>{self.interval}</interval>"
            "</EVENT>"
        )


@dataclass(slots=True)
class LifeCycleEvent(MetaEvent):
    """生命周期事件"""
    
    sub_type: LifeCycleSubType = LifeCycleSubType.ENABLE
    """生命周期子类型"""

    meta_event_type: str = field(default=MetaEventType.LIFECYCLE, init=False)
    """元事件类型(固定为生命周期)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> LifeCycleEvent:
        try:
            sub_type = LifeCycleSubType(data.get("sub_type", "enable"))
        except ValueError:
            sub_type = LifeCycleSubType.ENABLE
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            sub_type=sub_type,
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[生命周期] 机器人{self.sub_type.value}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>lifecycle</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<sub_type>{self.sub_type.value}</sub_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class NoticeEvent(OneBotEvent):
    """通知事件基类

    用于接收各类通知(好友添加、群组变动等)
    """
    notice_type: str = ""
    """通知类型"""

    post_type: PostType = field(default=PostType.NOTICE, init=False)
    """事件大类(固定为通知事件)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> NoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            notice_type=data.get("notice_type", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[通知] {self.notice_type}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>notice</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<notice_type>{self.notice_type}</notice_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupNoticeEvent(NoticeEvent):
    """群相关通知事件基类

    所有涉及群的通知事件都继承此类
    """
    group_id: int = 0
    """群号"""
    user_id: int = 0
    """用户 QQ 号"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            notice_type=data.get("notice_type", ""),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[群通知] 群{self.group_id} 用户{self.user_id} {self.notice_type}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_notice</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<notice_type>{self.notice_type}</notice_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupRecallNoticeEvent(GroupNoticeEvent):
    """群消息撤回通知"""
    operator_id: int = 0
    """操作者 QQ 号"""
    message_id: int = 0
    """被撤回的消息 ID"""

    notice_type: str = field(default=NoticeType.GROUP_RECALL, init=False)
    """通知类型(固定为群消息撤回)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupRecallNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            operator_id=data.get("operator_id", 0),
            message_id=data.get("message_id", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[群消息撤回] 群{self.group_id}中用户{self.user_id}撤回了消息{self.message_id}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_recall</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<operator_id>{self.operator_id}</operator_id>"
            f"<message_id>{self.message_id}</message_id>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupIncreaseEvent(GroupNoticeEvent):
    """群成员增加通知"""
    operator_id: int = 0
    """操作者 QQ 号"""
    sub_type: GroupIncreaseSubType = GroupIncreaseSubType.APPROVE
    """子类型：同意加群/邀请加群"""

    notice_type: str = field(default=NoticeType.GROUP_INCREASE, init=False)
    """通知类型(固定为群成员增加)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupIncreaseEvent:
        sub_str = data.get("sub_type", "approve")
        try:
            sub = GroupIncreaseSubType(sub_str)
        except ValueError:
            sub = GroupIncreaseSubType.APPROVE
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            operator_id=data.get("operator_id", 0),
            sub_type=sub,
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        sub_desc = {
            GroupIncreaseSubType.APPROVE: "通过审批",
            GroupIncreaseSubType.INVITE: "通过邀请",
        }.get(self.sub_type, self.sub_type.value)
        return f"[群成员增加] 用户{self.user_id}通过{sub_desc}加入了群{self.group_id}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_increase</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<operator_id>{self.operator_id}</operator_id>"
            f"<sub_type>{self.sub_type.value}</sub_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupDecreaseEvent(GroupNoticeEvent):
    """群成员减少通知"""
    operator_id: int = 0
    """操作者 QQ 号"""
    sub_type: GroupDecreaseSubType = GroupDecreaseSubType.LEAVE
    """子类型：主动退群/被踢/我被踢/群解散"""

    notice_type: str = field(default=NoticeType.GROUP_DECREASE, init=False)
    """通知类型(固定为群成员减少)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupDecreaseEvent:
        sub_str = data.get("sub_type", "leave")
        try:
            sub = GroupDecreaseSubType(sub_str)
        except ValueError:
            sub = GroupDecreaseSubType.LEAVE
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            operator_id=data.get("operator_id", 0),
            sub_type=sub,
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        sub_desc = {
            GroupDecreaseSubType.LEAVE: "退出了",
            GroupDecreaseSubType.KICK: "被踢出了",
            GroupDecreaseSubType.KICK_ME: "被踢出了",
            GroupDecreaseSubType.DISBAND: "解散了",
        }.get(self.sub_type, self.sub_type.value)
        return f"[群成员减少] 用户{self.user_id}{sub_desc}群{self.group_id}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_decrease</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<operator_id>{self.operator_id}</operator_id>"
            f"<sub_type>{self.sub_type.value}</sub_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupAdminNoticeEvent(GroupNoticeEvent):
    """群管理员变动通知"""
    sub_type: GroupAdminSubType = GroupAdminSubType.SET
    """子类型：设置/取消管理员"""

    notice_type: str = field(default=NoticeType.GROUP_ADMIN, init=False)
    """通知类型(固定为群管理员变动)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupAdminNoticeEvent:
        sub_str = data.get("sub_type", "set")
        try:
            sub = GroupAdminSubType(sub_str)
        except ValueError:
            sub = GroupAdminSubType.SET
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            sub_type=sub,
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        sub_desc = {
            GroupAdminSubType.SET: "被设为管理员的",
            GroupAdminSubType.UNSET: "被取消管理员的",
        }.get(self.sub_type, self.sub_type.value)
        return f"[群管理员变动] 用户{self.user_id}在群{self.group_id}{sub_desc}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_admin</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<sub_type>{self.sub_type.value}</sub_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupBanEvent(GroupNoticeEvent):
    """群禁言通知"""
    operator_id: int = 0
    """操作者 QQ 号"""
    duration: int = 0
    """禁言时长(秒)"""
    sub_type: GroupBanSubType = GroupBanSubType.BAN
    """子类型：禁言/解除禁言"""

    notice_type: str = field(default=NoticeType.GROUP_BAN, init=False)
    """通知类型(固定为群禁言)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupBanEvent:
        sub_str = data.get("sub_type", "ban")
        try:
            sub = GroupBanSubType(sub_str)
        except ValueError:
            sub = GroupBanSubType.BAN
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            operator_id=data.get("operator_id", 0),
            duration=data.get("duration", 0),
            sub_type=sub,
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        if self.sub_type == GroupBanSubType.BAN:
            return f"[群禁言] 用户{self.user_id}在群{self.group_id}被管理员{self.operator_id}禁言{self.duration}秒"
        else:
            return f"[群禁言] 用户{self.user_id}在群{self.group_id}被管理员{self.operator_id}解除禁言"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_ban</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<operator_id>{self.operator_id}</operator_id>"
            f"<duration>{self.duration}</duration>"
            f"<sub_type>{self.sub_type.value}</sub_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupUploadNoticeEvent(GroupNoticeEvent):
    """群文件上传通知"""
    file: Dict[str, Any] = field(default_factory=dict)
    """文件信息"""

    notice_type: str = field(default=NoticeType.GROUP_UPLOAD, init=False)
    """通知类型(固定为群文件上传)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupUploadNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            file=data.get("file", {}),
            primeval=data,
        )

    @property
    def file_id(self) -> str:
        return self.file.get("id", "")

    @property
    def file_name(self) -> str:
        return self.file.get("name", "")

    @property
    def file_size(self) -> int:
        return self.file.get("size", 0)

    @property
    def file_busid(self) -> int:
        return self.file.get("busid", 0)

    def _format_event_simple(self) -> str:
        return f"[群文件上传] 用户{self.user_id}在群{self.group_id}上传了文件{self.file_name}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_upload</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<file_id>{self.file_id}</file_id>"
            f"<file_name>{self.file_name}</file_name>"
            f"<file_size>{self.file_size}</file_size>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupCardEvent(GroupNoticeEvent):
    """群名片变更通知"""
    card_new: str = ""
    """新名片"""
    card_old: str = ""
    """旧名片"""

    notice_type: str = field(default=NoticeType.GROUP_CARD, init=False)
    """通知类型(固定为群名片变更)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupCardEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            card_new=data.get("card_new", ""),
            card_old=data.get("card_old", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[群名片变更] 用户{self.user_id}在群{self.group_id}将名片从'{self.card_old}'改为'{self.card_new}'"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_card</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<card_old>{self.card_old}</card_old>"
            f"<card_new>{self.card_new}</card_new>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupNameEvent(GroupNoticeEvent):
    """群名变更通知"""
    name_new: str = ""
    """新群名"""
    name_old: str = ""
    """旧群名"""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
    """通知类型(固定为 notify)"""
    # sub_type = "group_name" 由 primeval 保留

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupNameEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            name_new=data.get("name_new", ""),
            name_old=data.get("name_old", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[群名变更] 群{self.group_id}的名称从'{self.name_old}'改为'{self.name_new}'"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>群名变更</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<name_old>{self.name_old}</name_old>"
            f"<name_new>{self.name_new}</name_new>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupTitleEvent(GroupNoticeEvent):
    """群头衔变更通知"""
    title: str = ""
    """新头衔"""
    title_old: str = ""
    """旧头衔"""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
    """通知类型(固定为 notify)"""
    # sub_type = "title" 由 primeval 保留

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupTitleEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            title=data.get("title", ""),
            title_old=data.get("title_old", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[群头衔变更] 用户{self.user_id}在群{self.group_id}头衔从'{self.title_old}'改为'{self.title}'"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>群头衔变更</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<title_old>{self.title_old}</title_old>"
            f"<title>{self.title}</title>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupEssenceEvent(GroupNoticeEvent):
    """群精华消息通知"""
    message_id: int = 0
    """消息 ID"""
    sender_id: int = 0
    """消息发送者 QQ 号"""
    operator_id: int = 0
    """操作者 QQ 号"""
    sub_type: EssenceSubType = EssenceSubType.ADD
    """子类型：添加/删除精华"""

    notice_type: str = field(default=NoticeType.ESSENCE, init=False)
    """通知类型(固定为精华消息)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupEssenceEvent:
        sub_str = data.get("sub_type", "add")
        try:
            sub = EssenceSubType(sub_str)
        except ValueError:
            sub = EssenceSubType.ADD
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            message_id=data.get("message_id", 0),
            sender_id=data.get("sender_id", 0),
            operator_id=data.get("operator_id", 0),
            sub_type=sub,
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        sub_desc = {
            EssenceSubType.ADD: "被设为精华",
            EssenceSubType.DELETE: "被取消精华",
        }.get(self.sub_type, self.sub_type.value)
        return f"[精华消息] 群{self.group_id}消息{self.message_id}{sub_desc}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_essence</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<message_id>{self.message_id}</message_id>"
            f"<sender_id>{self.sender_id}</sender_id>"
            f"<operator_id>{self.operator_id}</operator_id>"
            f"<sub_type>{self.sub_type.value}</sub_type>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupMsgEmojiLikeEvent(GroupNoticeEvent):
    """表情回应通知"""
    message_id: int = 0
    """消息 ID"""
    likes: List[Dict[str, Any]] = field(default_factory=list)
    """表情信息列表"""

    notice_type: str = field(default=NoticeType.GROUP_MSG_EMOJI_LIKE, init=False)
    """通知类型(固定为表情回应)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupMsgEmojiLikeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            message_id=data.get("message_id", 0),
            likes=data.get("likes", []),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[表情回应] 用户{self.user_id}在群{self.group_id}对消息{self.message_id}使用了表情回应"

    def _format_event_detailed(self) -> str:
        import json
        return (
            "<EVENT>"
            f"<type>group_msg_emoji_like</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<message_id>{self.message_id}</message_id>"
            f"<likes>{json.dumps(self.likes, ensure_ascii=False)}</likes>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupGrayTipEvent(NoticeEvent):
    """群灰条消息通知"""
    group_id: int = 0
    """收取群号"""
    user_id: int = 0
    """真实发送者 QQ"""
    message_id: int = 0
    """消息 ID"""
    busi_id: str = ""
    """业务 ID"""
    content: str = ""
    """灰条内容(JSON 字符串)"""
    raw_info: Any = None
    """原始信息"""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
    """通知类型(固定为 notify)"""
    # sub_type = "gray_tip" 由 primeval 保留

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupGrayTipEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            group_id=data.get("group_id", 0),
            user_id=data.get("user_id", 0),
            message_id=data.get("message_id", 0),
            busi_id=data.get("busi_id", ""),
            content=data.get("content", ""),
            raw_info=data.get("raw_info"),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        content_preview = self.content[:200] if self.content else ""
        return f"[灰条提示] 群{self.group_id}: {content_preview}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>gray_tip</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<message_id>{self.message_id}</message_id>"
            f"<content>{self.content[:500]}</content>"
            "</EVENT>"
        )


@dataclass(slots=True)
class FriendAddNoticeEvent(NoticeEvent):
    """好友添加通知"""
    user_id: int = 0
    """新好友 QQ 号"""

    notice_type: str = field(default=NoticeType.FRIEND_ADD, init=False)
    """通知类型(固定为好友添加)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> FriendAddNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[好友添加] 用户{self.user_id}已成为好友"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>friend_add</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            "</EVENT>"
        )


@dataclass(slots=True)
class FriendRecallNoticeEvent(NoticeEvent):
    """好友消息撤回通知"""
    user_id: int = 0
    """消息发送者 QQ 号"""
    message_id: int = 0
    """被撤回的消息 ID"""

    notice_type: str = field(default=NoticeType.FRIEND_RECALL, init=False)
    """通知类型(固定为好友消息撤回)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> FriendRecallNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            message_id=data.get("message_id", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[好友消息撤回] 好友{self.user_id}撤回了消息{self.message_id}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>消息撤回</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<message_id>{self.message_id}</message_id>"
            "</EVENT>"
        )


@dataclass(slots=True)
class PokeEvent(NoticeEvent):
    """戳一戳通知基类"""
    user_id: int = 0
    """戳者 QQ 号"""
    target_id: int = 0
    """被戳者 QQ 号"""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
    """通知类型(固定为 notify)"""
    # sub_type = "poke" 由 primeval 保留

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> PokeEvent:
        if "group_id" in data:
            return GroupPokeEvent.from_data(data)
        else:
            return FriendPokeEvent.from_data(data)

    @classmethod
    def _base_from_data(cls, data: Dict[str, Any]) -> PokeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            target_id=data.get("target_id", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[戳一戳] 用户{self.user_id}戳了戳{self.target_id}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>戳一戳</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<target_id>{self.target_id}</target_id>"
            "</EVENT>"
        )


@dataclass(slots=True)
class FriendPokeEvent(PokeEvent):
    """好友戳一戳通知"""
    sender_id: int = 0
    """发送者 QQ 号"""
    raw_info: Any = None
    """原始信息"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> FriendPokeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            target_id=data.get("target_id", 0),
            sender_id=data.get("sender_id", 0),
            raw_info=data.get("raw_info"),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[好友戳一戳] 用户{self.user_id}戳了戳你"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>好友戳一戳你</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupPokeEvent(PokeEvent):
    """群戳一戳通知"""
    group_id: int = 0
    """群号"""
    raw_info: Any = None
    """原始信息"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupPokeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            target_id=data.get("target_id", 0),
            group_id=data.get("group_id", 0),
            raw_info=data.get("raw_info"),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[群戳一戳] 用户{self.user_id}在群{self.group_id}戳了戳{self.target_id}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>群戳一戳/type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<target_id>{self.target_id}</target_id>"
            "</EVENT>"
        )


@dataclass(slots=True)
class ProfileLikeEvent(NoticeEvent):
    """个人资料点赞通知"""
    operator_id: int = 0
    """操作者 QQ 号"""
    operator_nick: str = ""
    """操作者昵称"""
    times: int = 0
    """点赞次数"""
    _like_time: int = 0
    """点赞时间戳"""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
    """通知类型(固定为 notify)"""
    # sub_type = "profile_like" 由 primeval 保留

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> ProfileLikeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            operator_id=data.get("operator_id", 0),
            operator_nick=data.get("operator_nick", ""),
            times=data.get("times", 0),
            _like_time=data.get("time", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[资料点赞] {self.operator_nick}({self.operator_id})给你点了{self.times}个赞"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>profile_like</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<operator_id>{self.operator_id}</operator_id>"
            f"<operator_nick>{self.operator_nick}</operator_nick>"
            f"<times>{self.times}</times>"
            "</EVENT>"
        )


@dataclass(slots=True)
class InputStatusEvent(NoticeEvent):
    """输入状态通知"""
    user_id: int = 0
    """用户 QQ 号"""
    group_id: int = 0
    """群号"""
    status_text: str = ""
    """状态文本"""
    event_type: int = 0
    """事件类型"""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
    """通知类型(固定为 notify)"""
    # sub_type = "input_status" 由 primeval 保留

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> InputStatusEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            group_id=data.get("group_id", 0),
            status_text=data.get("status_text", ""),
            event_type=data.get("event_type", 0),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[输入状态] 用户{self.user_id}在群{self.group_id}: {self.status_text}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>input_status</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<status_text>{self.status_text}</status_text>"
            "</EVENT>"
        )


@dataclass(slots=True)
class BotOfflineEvent(NoticeEvent):
    """机器人离线通知"""
    user_id: int = 0
    """机器人 QQ 号"""
    tag: str = ""
    """标签"""
    message: str = ""
    """离线消息"""

    notice_type: str = field(default=NoticeType.BOT_OFFLINE, init=False)
    """通知类型(固定为机器人离线)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> BotOfflineEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            tag=data.get("tag", ""),
            message=data.get("message", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[机器人离线] {self.message}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>bot_offline</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<message>{self.message}</message>"
            "</EVENT>"
        )


@dataclass(slots=True)
class RequestEvent(OneBotEvent):
    """请求事件基类

    用于处理各类需要回应的请求(好友请求、加群请求等)
    """
    request_type: str = ""
    """请求类型"""
    comment: str = ""
    """验证信息"""
    flag: str = ""
    """请求标识"""
    user_id:int = 0

    post_type: PostType = field(default=PostType.REQUEST, init=False)
    """事件大类(固定为请求事件)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> RequestEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            request_type=data.get("request_type", ""),
            user_id=data.get("user_id", 0),
            comment=data.get("comment", ""),
            flag=data.get("flag", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[请求] 用户{self.user_id} {self.request_type}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>request</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<request_type>{self.request_type}</request_type>"
            f"<user_id>{self.user_id}</user_id>"
            f"<comment>{self.comment[:500]}</comment>"
            f"<flag>{self.flag}</flag>"
            "</EVENT>"
        )


@dataclass(slots=True)
class FriendRequestEvent(RequestEvent):
    """好友请求事件"""
    request_type: str = field(default=RequestType.FRIEND, init=False)
    """请求类型(固定为好友请求)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> FriendRequestEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            comment=data.get("comment", ""),
            flag=data.get("flag", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[好友请求] 用户{self.user_id}请求添加好友: {self.comment[:200]}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>friend_request</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<comment>{self.comment[:500]}</comment>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupRequestEvent(RequestEvent):
    """群请求事件(加群请求 / 邀请入群)"""
    group_id: int = 0
    """群号"""
    sub_type: str = ""
    """请求子类型"""

    request_type: str = field(default=RequestType.GROUP, init=False)
    """请求类型(固定为群请求)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupRequestEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            comment=data.get("comment", ""),
            flag=data.get("flag", ""),
            group_id=data.get("group_id", 0),
            sub_type=data.get("sub_type", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        sub_desc = {
            "add": "加入",
            "invite": "邀请入群",
        }.get(self.sub_type, self.sub_type)
        return f"[群请求] 用户{self.user_id}请求{sub_desc}群{self.group_id}: {self.comment[:200]}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_request</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<comment>{self.comment[:500]}</comment>"
            "</EVENT>"
        )


@dataclass(slots=True)
class MessageEvent(OneBotEvent):
    """消息事件基类

    所有聊天消息(私聊、群聊、自身发送)的基类
    """
    message_id: int = 0
    """消息唯一 ID"""
    user_id: int = 0
    """发送者 QQ 号"""
    segments: List[MessageSegment] = field(default_factory=list)
    """解析后的消息段对象列表"""
    raw_message: str = ""
    """原始 CQ 码文本"""
    sender: Dict[str, Any] = field(default_factory=dict)
    """发送者信息字典"""

    post_type: PostType = field(default=PostType.MESSAGE, init=False)
    """事件大类(固定为消息事件)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> MessageEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            message_id=data.get("message_id", 0),
            user_id=data.get("user_id", 0),
            segments=parse_onebot_segments(data.get("message", [])),
            raw_message=data.get("raw_message", ""),
            sender=data.get("sender", {}),
            primeval=data,
        )

    @property
    def sender_nickname(self) -> str:
        """发送者昵称"""
        return self.sender.get("nickname", "")

    @property
    def pure_text(self) -> str:
        """提取消息中的纯文本"""
        return "".join(
            s.text for s in self.segments
            if isinstance(s, TextSegment)
        )

    @property
    def cq_code(self) -> str:
        """获取简略的 CQ 码表示"""
        return "".join(s.__str__() for s in self.segments)

    def _format_event_simple(self) -> str:
        return f"[消息] 用户{self.user_id}: {self.pure_text[:150]}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<message_id>{self.message_id}</message_id>"
            f"<message>{self.cq_code[:TEXT_LENGTH_LIMIT]}</message>"
            f"<nickname>{self.sender_nickname}</nickname>"
            "</EVENT>"
        )

    def to_chat_message(self):
        """将 MessageEvent 转换为现有的 ChatMessage 对象

        这是新旧类型体系之间的桥接方法。新的平台适配器应优先使用事件类型本身，
        但在需要与现有处理链路(GroupChat / PrivateChat / CommandSystem 等)
        交互时，可通过此方法获取 ChatMessage

        Returns:
            ChatMessage: 等价的 ChatMessage 实例
        """
        pure_text = "".join(
            s.text for s in self.segments
            if isinstance(s, TextSegment)
        )

        return ChatMessage(
            self_id=self.self_id,
            user_id=self.user_id,
            group_id=getattr(self, "group_id", None),
            message_id=self.message_id,
            time=self.time,
            primeval=self.primeval,
            raw_message=self.raw_message,
            user_cq_message=self.cq_code,
            llm_formatted_message="",
            pure_text=pure_text,
            segments=self.segments,
            sender_info=self.sender,
        )


@dataclass(slots=True)
class PrivateMessageEvent(MessageEvent):
    """私聊消息事件"""
    message_type: str = field(default=MessageType.PRIVATE, init=False)
    """消息类型(固定为私聊)"""
    sub_type: str = ""
    """子类型：好友/群临时会话/其他"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> PrivateMessageEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            message_id=data.get("message_id", 0),
            user_id=data.get("user_id", 0),
            segments=parse_onebot_segments(data.get("message", [])),
            raw_message=data.get("raw_message", ""),
            sender=data.get("sender", {}),
            sub_type=data.get("sub_type", ""),
            primeval=data,
        )

    def _format_event_simple(self) -> str:
        return f"[私聊消息] 用户{self.user_id}({self.sender_nickname}): {self.pure_text[:200]}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>private_message</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<nickname>{self.sender_nickname}</nickname>"
            f"<message_id>{self.message_id}</message_id>"
            f"<sub_type>{self.sub_type}</sub_type>"
            f"<message>{self.cq_code[:TEXT_LENGTH_LIMIT]}</message>"
            "</EVENT>"
        )


@dataclass(slots=True)
class GroupMessageEvent(MessageEvent):
    """群聊消息事件"""
    group_id: int = 0
    """群号"""
    anonymous: Any = None
    """匿名信息"""

    message_type: str = field(default=MessageType.GROUP, init=False)
    """消息类型(固定为群聊)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> GroupMessageEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            message_id=data.get("message_id", 0),
            user_id=data.get("user_id", 0),
            segments=parse_onebot_segments(data.get("message", [])),
            raw_message=data.get("raw_message", ""),
            sender=data.get("sender", {}),
            group_id=data.get("group_id", 0),
            anonymous=data.get("anonymous"),
            primeval=data,
        )

    @property
    def sender_card(self) -> str:
        """发送者群名片"""
        return self.sender.get("card", "")

    @property
    def sender_role(self) -> str:
        """发送者群角色 (owner / admin / member)"""
        return self.sender.get("role", "member")

    @property
    def sender_title(self) -> str:
        """发送者专属头衔"""
        return self.sender.get("title", "")

    @property
    def sender_level(self) -> str:
        """发送者成员等级"""
        return self.sender.get("level", "")

    def to_chat_message(self):
        """转换为 ChatMessage(群聊版)"""
        pure_text = "".join(
            s.text for s in self.segments
            if isinstance(s, TextSegment)
        )

        return ChatMessage(
            self_id=self.self_id,
            user_id=self.user_id,
            group_id=self.group_id,
            message_id=self.message_id,
            time=self.time,
            primeval=self.primeval,
            raw_message=self.raw_message,
            user_cq_message=self.cq_code,
            llm_formatted_message="",
            pure_text=pure_text,
            segments=self.segments,
            sender_info=self.sender,
        )

    def _format_event_simple(self) -> str:
        card = self.sender_card or self.sender_nickname or ""
        name_part = f"({card})" if card else ""
        return f"[群聊消息] 群{self.group_id} 用户{self.user_id}{name_part}: {self.pure_text[:200]}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<type>group_message</type>"
            f"<time>{self._fmt_time()}</time>"
            f"<group_id>{self.group_id}</group_id>"
            f"<user_id>{self.user_id}</user_id>"
            f"<nickname>{self.sender_nickname}</nickname>"
            f"<sender_card>{self.sender_card}</sender_card>"
            f"<sender_role>{self.sender_role}</sender_role>"
            f"<message_id>{self.message_id}</message_id>"
            f"<message>{self.cq_code[:TEXT_LENGTH_LIMIT]}</message>"
            "</EVENT>"
        )


@dataclass(slots=True)
class MessageSentEvent(MessageEvent):
    """自身消息发送事件(机器人发出的消息回执)"""
    group_id:int = None
    """群号(私聊时为 None)"""
    message_type: str = ""
    """消息类型:private 或 group"""
    target_id: int = 0
    """目标 ID(好友 QQ 号或群号)"""

    post_type: PostType = field(default=PostType.MESSAGE_SENT, init=False)
    """事件大类(固定为消息发送事件)"""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> MessageSentEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            message_id=data.get("message_id", 0),
            user_id=data.get("user_id", 0),
            group_id = data.get("group_id", 0),
            segments=parse_onebot_segments(data.get("message", [])),
            raw_message=data.get("raw_message", ""),
            sender=data.get("sender", {}),
            message_type=data.get("message_type", ""),
            target_id=data.get("target_id", 0),
            primeval=data,
        )

    def to_chat_message(self):
        """转换为 ChatMessage(自身消息版)

        注意: 自身消息不保证包含标准 sender 结构
        """
        pure_text = "".join(
            s.text for s in self.segments
            if isinstance(s, TextSegment)
        )

        return ChatMessage(
            self_id=self.self_id,
            user_id=self.user_id,
            group_id=self.group_id,
            message_id=self.message_id,
            time=self.time,
            primeval=self.primeval,
            raw_message=self.raw_message,
            user_cq_message=self.cq_code,
            llm_formatted_message="",
            pure_text=pure_text,
            segments=self.segments,
            sender_info=self.sender,
        )

    def _format_event_simple(self) -> str:
        dest = self.group_id or self.user_id
        return f"[已发送消息] → {dest}: {self.pure_text[:200]}"

    def _format_event_detailed(self) -> str:
        return (
            "<EVENT>"
            f"<time>{self._fmt_time()}</time>"
            f"<user_id>{self.user_id}</user_id>"
            f"<group_id>{self.group_id}</group_id>"
            f"<target_id>{self.target_id}</target_id>"
            f"<message_id>{self.message_id}</message_id>"
            f"<message>{self.cq_code[:TEXT_LENGTH_LIMIT]}</message>"
            "</EVENT>"
        )


# 所有消息类事件
AnyMessageEvent = PrivateMessageEvent | GroupMessageEvent | MessageSentEvent

# 所有通知类事件
AnyNoticeEvent = (
    GroupRecallNoticeEvent | GroupIncreaseEvent | GroupDecreaseEvent |
    GroupAdminNoticeEvent | GroupBanEvent | GroupUploadNoticeEvent |
    GroupCardEvent | GroupNameEvent | GroupTitleEvent | GroupEssenceEvent |
    GroupMsgEmojiLikeEvent | GroupGrayTipEvent |
    FriendAddNoticeEvent | FriendRecallNoticeEvent |
    FriendPokeEvent | GroupPokeEvent |
    ProfileLikeEvent | InputStatusEvent | BotOfflineEvent
)

# 所有请求类事件
AnyRequestEvent = FriendRequestEvent | GroupRequestEvent

# 所有元事件
AnyMetaEvent = HeartbeatEvent | LifeCycleEvent
