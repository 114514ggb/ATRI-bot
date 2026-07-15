import time
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from atribot.core.type.chat_message_types import (
    ChatMessage,
    MessageSegment,
    TextSegment,
    parse_onebot_segments,
)


class PostType(str, Enum):
    """事件大类"""
    META = "meta_event"
    MESSAGE = "message"
    MESSAGE_SENT = "message_sent"
    NOTICE = "notice"
    REQUEST = "request"


class MetaEventType(str, Enum):
    """元事件子类型"""
    HEARTBEAT = "heartbeat"
    LIFECYCLE = "lifecycle"


class LifeCycleSubType(str, Enum):
    """生命周期子类型"""
    ENABLE = "enable"
    DISABLE = "disable"
    CONNECT = "connect"


class NoticeType(str, Enum):
    """通知事件子类型"""
    FRIEND_ADD = "friend_add"
    FRIEND_RECALL = "friend_recall"
    GROUP_RECALL = "group_recall"
    GROUP_INCREASE = "group_increase"
    GROUP_DECREASE = "group_decrease"
    GROUP_ADMIN = "group_admin"
    GROUP_BAN = "group_ban"
    GROUP_UPLOAD = "group_upload"
    GROUP_CARD = "group_card"
    NOTIFY = "notify"            # 通用通知(子类型由 sub_type 区分)
    ESSENCE = "essence"
    GROUP_MSG_EMOJI_LIKE = "group_msg_emoji_like"
    BOT_OFFLINE = "bot_offline"


class NotifySubType(str, Enum):
    """notify 类通知的 sub_type 值"""
    POKE = "poke"
    PROFILE_LIKE = "profile_like"
    INPUT_STATUS = "input_status"
    GROUP_NAME = "group_name"
    TITLE = "title"
    GRAY_TIP = "gray_tip"


class GroupDecreaseSubType(str, Enum):
    """群成员减少子类型"""
    LEAVE = "leave"
    KICK = "kick"
    KICK_ME = "kick_me"
    DISBAND = "disband"


class GroupIncreaseSubType(str, Enum):
    """群成员增加子类型"""
    APPROVE = "approve"
    INVITE = "invite"


class GroupAdminSubType(str, Enum):
    """群管理员变动子类型"""
    SET = "set"
    UNSET = "unset"


class GroupBanSubType(str, Enum):
    """群禁言子类型"""
    BAN = "ban"
    LIFT_BAN = "lift_ban"


class EssenceSubType(str, Enum):
    """精华消息子类型"""
    ADD = "add"
    DELETE = "delete"


class MessageType(str, Enum):
    """消息类型(message_type)"""
    PRIVATE = "private"
    GROUP = "group"


class PrivateSubType(str, Enum):
    """私聊消息子类型"""
    FRIEND = "friend"
    GROUP = "group"
    OTHER = "other"


class SenderRole(str, Enum):
    """群成员角色"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class SenderSex(str, Enum):
    """性别"""
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class RequestType(str, Enum):
    """请求事件子类型"""
    FRIEND = "friend"
    GROUP = "group"


@dataclass(slots=True)
class OneBotEvent(ABC):
    """所有 OneBot 事件的抽象基类

    定义了所有事件的共有字段，并提供 from_dict() 工厂方法自动分发到正确的子类

    Attributes:
        time: 事件发生的时间戳(Unix 秒)
        self_id: 机器人自身 QQ 号
        post_type: 事件大类
        primeval: 原始事件 JSON 字典(完整保留，用于兼容和调试)
    """
    time: int
    self_id: int
    post_type: PostType
    primeval: Dict[str, Any] = field(repr=False, default_factory=dict)

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

        if post_type == PostType.META:
            return cls._parse_meta(data)
        elif post_type == PostType.MESSAGE:
            return cls._parse_message(data)
        elif post_type == PostType.MESSAGE_SENT:
            return cls._parse_message_sent(data)
        elif post_type == PostType.NOTICE:
            return cls._parse_notice(data)
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
        if message_type == MessageType.PRIVATE:
            return PrivateMessageEvent.from_data(data)
        elif message_type == MessageType.GROUP:
            return GroupMessageEvent.from_data(data)
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
        if notice_type == NoticeType.GROUP_RECALL:
            return GroupRecallNoticeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_INCREASE:
            return GroupIncreaseEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_DECREASE:
            return GroupDecreaseEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_MSG_EMOJI_LIKE:
            return GroupMsgEmojiLikeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_ADMIN:
            return GroupAdminNoticeEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_BAN:
            return GroupBanEvent.from_data(data)
        elif notice_type == NoticeType.GROUP_UPLOAD:
            return GroupUploadNoticeEvent.from_data(data)
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
        elif notice_type == NoticeType.FRIEND_ADD:
            return FriendAddNoticeEvent.from_data(data)
        elif notice_type == NoticeType.FRIEND_RECALL:
            return FriendRecallNoticeEvent.from_data(data)

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

    post_type: PostType = field(default=PostType.META, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> MetaEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            meta_event_type=data.get("meta_event_type", ""),
            primeval=data,
        )


@dataclass(slots=True)
class HeartbeatEvent(MetaEvent):
    """心跳事件

    NapCat 定期发送，用于确认连接状态

    Attributes:
        status: 状态信息 {"online": bool, "good": bool}
        interval: 心跳间隔(毫秒)
    """
    status: Dict[str, Any] = field(default_factory=dict)
    interval: int = 0

    meta_event_type: str = field(default=MetaEventType.HEARTBEAT, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> "HeartbeatEvent":
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


@dataclass(slots=True)
class LifeCycleEvent(MetaEvent):
    """生命周期事件

    NapCat 启用、禁用或连接时触发
    """
    sub_type: LifeCycleSubType = LifeCycleSubType.ENABLE

    meta_event_type: str = field(default=MetaEventType.LIFECYCLE, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> "LifeCycleEvent":
        sub_type_str = data.get("sub_type", "enable")
        try:
            sub_type = LifeCycleSubType(sub_type_str)
        except ValueError:
            sub_type = LifeCycleSubType.ENABLE
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            sub_type=sub_type,
            primeval=data,
        )


@dataclass(slots=True)
class NoticeEvent(OneBotEvent):
    """通知事件基类

    用于接收各类通知(好友添加、群组变动等)
    """
    notice_type: str = ""

    post_type: PostType = field(default=PostType.NOTICE, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> NoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            notice_type=data.get("notice_type", ""),
            primeval=data,
        )


@dataclass(slots=True)
class GroupNoticeEvent(NoticeEvent):
    """群相关通知事件基类

    所有涉及群的通知事件都继承此类
    """
    group_id: int = 0
    user_id: int = 0

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


@dataclass(slots=True)
class GroupRecallNoticeEvent(GroupNoticeEvent):
    """群消息撤回通知"""
    operator_id: int = 0
    message_id: int = 0

    notice_type: str = field(default=NoticeType.GROUP_RECALL, init=False)

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


@dataclass(slots=True)
class GroupIncreaseEvent(GroupNoticeEvent):
    """群成员增加通知"""
    operator_id: int = 0
    sub_type: GroupIncreaseSubType = GroupIncreaseSubType.APPROVE

    notice_type: str = field(default=NoticeType.GROUP_INCREASE, init=False)

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


@dataclass(slots=True)
class GroupDecreaseEvent(GroupNoticeEvent):
    """群成员减少通知"""
    operator_id: int = 0
    sub_type: GroupDecreaseSubType = GroupDecreaseSubType.LEAVE

    notice_type: str = field(default=NoticeType.GROUP_DECREASE, init=False)

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


@dataclass(slots=True)
class GroupAdminNoticeEvent(GroupNoticeEvent):
    """群管理员变动通知"""
    sub_type: GroupAdminSubType = GroupAdminSubType.SET

    notice_type: str = field(default=NoticeType.GROUP_ADMIN, init=False)

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


@dataclass(slots=True)
class GroupBanEvent(GroupNoticeEvent):
    """群禁言通知"""
    operator_id: int = 0
    duration: int = 0
    sub_type: GroupBanSubType = GroupBanSubType.BAN

    notice_type: str = field(default=NoticeType.GROUP_BAN, init=False)

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


@dataclass(slots=True)
class GroupUploadNoticeEvent(GroupNoticeEvent):
    """群文件上传通知"""
    file: Dict[str, Any] = field(default_factory=dict)

    notice_type: str = field(default=NoticeType.GROUP_UPLOAD, init=False)

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


@dataclass(slots=True)
class GroupCardEvent(GroupNoticeEvent):
    """群名片变更通知"""
    card_new: str = ""
    card_old: str = ""

    notice_type: str = field(default=NoticeType.GROUP_CARD, init=False)

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


@dataclass(slots=True)
class GroupNameEvent(GroupNoticeEvent):
    """群名变更通知"""
    name_new: str = ""
    name_old: str = ""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
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


@dataclass(slots=True)
class GroupTitleEvent(GroupNoticeEvent):
    """群头衔变更通知"""
    title: str = ""
    title_old: str = ""

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
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


@dataclass(slots=True)
class GroupEssenceEvent(GroupNoticeEvent):
    """群精华消息通知"""
    message_id: int = 0
    sender_id: int = 0
    operator_id: int = 0
    sub_type: EssenceSubType = EssenceSubType.ADD

    notice_type: str = field(default=NoticeType.ESSENCE, init=False)

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


@dataclass(slots=True)
class GroupMsgEmojiLikeEvent(GroupNoticeEvent):
    """表情回应通知"""
    message_id: int = 0
    likes: List[Dict[str, Any]] = field(default_factory=list)

    notice_type: str = field(default=NoticeType.GROUP_MSG_EMOJI_LIKE, init=False)

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


@dataclass(slots=True)
class GroupGrayTipEvent(NoticeEvent):
    """群灰条消息通知"""
    group_id: int = 0
    user_id: int = 0
    message_id: int = 0
    busi_id: str = ""
    content: str = ""
    raw_info: Any = None

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
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


@dataclass(slots=True)
class FriendAddNoticeEvent(NoticeEvent):
    """好友添加通知"""
    user_id: int = 0

    notice_type: str = field(default=NoticeType.FRIEND_ADD, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> FriendAddNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            primeval=data,
        )


@dataclass(slots=True)
class FriendRecallNoticeEvent(NoticeEvent):
    """好友消息撤回通知"""
    user_id: int = 0
    message_id: int = 0

    notice_type: str = field(default=NoticeType.FRIEND_RECALL, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> FriendRecallNoticeEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            user_id=data.get("user_id", 0),
            message_id=data.get("message_id", 0),
            primeval=data,
        )


@dataclass(slots=True)
class PokeEvent(NoticeEvent):
    """戳一戳通知基类"""
    user_id: int = 0
    target_id: int = 0

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
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


@dataclass(slots=True)
class FriendPokeEvent(PokeEvent):
    """好友戳一戳通知"""
    sender_id: int = 0
    raw_info: Any = None

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


@dataclass(slots=True)
class GroupPokeEvent(PokeEvent):
    """群戳一戳通知"""
    group_id: int = 0
    raw_info: Any = None

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


@dataclass(slots=True)
class ProfileLikeEvent(NoticeEvent):
    """个人资料点赞通知"""
    operator_id: int = 0
    operator_nick: str = ""
    times: int = 0
    _like_time: int = 0

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
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


@dataclass(slots=True)
class InputStatusEvent(NoticeEvent):
    """输入状态通知"""
    user_id: int = 0
    group_id: int = 0
    status_text: str = ""
    event_type: int = 0

    notice_type: str = field(default=NoticeType.NOTIFY, init=False)
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


@dataclass(slots=True)
class BotOfflineEvent(NoticeEvent):
    """机器人离线通知"""
    user_id: int = 0
    tag: str = ""
    message: str = ""

    notice_type: str = field(default=NoticeType.BOT_OFFLINE, init=False)

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


@dataclass(slots=True)
class RequestEvent(OneBotEvent):
    """请求事件基类

    用于处理各类需要回应的请求(好友请求、加群请求等)
    """
    request_type: str = ""
    user_id: int = 0
    comment: str = ""
    flag: str = ""

    post_type: PostType = field(default=PostType.REQUEST, init=False)

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


@dataclass(slots=True)
class FriendRequestEvent(RequestEvent):
    """好友请求事件"""
    request_type: str = field(default=RequestType.FRIEND, init=False)

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


@dataclass(slots=True)
class GroupRequestEvent(RequestEvent):
    """群请求事件(加群请求 / 邀请入群)"""
    group_id: int = 0
    sub_type: str = ""

    request_type: str = field(default=RequestType.GROUP, init=False)

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


@dataclass(slots=True)
class MessageEvent(OneBotEvent):
    """消息事件基类

    所有聊天消息(私聊、群聊、自身发送)的基类

    Attributes:
        message_id: 消息唯一 ID
        user_id: 发送者 QQ 号
        segments: 解析后的消息段对象列表
        raw_message: 原始 CQ 码文本
        sender: 发送者信息字典
    """
    message_id: int = 0
    user_id: int = 0
    segments: List[MessageSegment] = field(default_factory=list)
    raw_message: str = ""
    sender: Dict[str, Any] = field(default_factory=dict)

    post_type: PostType = field(default=PostType.MESSAGE, init=False)

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
    def sender_user_id(self) -> int:
        """发送者 QQ 号"""
        return self.sender.get("user_id", self.user_id)

    @property
    def pure_text(self) -> str:
        """提取消息中的纯文本(从 segments 派生)"""
        return "".join(
            s.text for s in self.segments
            if isinstance(s, TextSegment)
        )

    @property
    def cq_code(self) -> str:
        """获取完整的 CQ 码表示(从 segments 派生)"""
        return "".join(str(s) for s in self.segments)

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
    sub_type: str = ""

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


@dataclass(slots=True)
class GroupMessageEvent(MessageEvent):
    """群聊消息事件"""
    group_id: int = 0
    anonymous: Any = None

    message_type: str = field(default=MessageType.GROUP, init=False)

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
        from atribot.core.type.chat_message_types import ChatMessage

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


@dataclass(slots=True)
class MessageSentEvent(MessageEvent):
    """自身消息发送事件(机器人发出的消息回执)"""
    message_type: str = ""
    target_id: int = 0

    post_type: PostType = field(default=PostType.MESSAGE_SENT, init=False)

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> MessageSentEvent:
        return cls(
            time=data.get("time", int(time.time())),
            self_id=data.get("self_id", 0),
            message_id=data.get("message_id", 0),
            user_id=data.get("user_id", 0),
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
        from atribot.core.type.chat_message_types import ChatMessage

        pure_text = "".join(
            s.text for s in self.segments
            if isinstance(s, TextSegment)
        )

        return ChatMessage(
            self_id=self.self_id,
            user_id=self.user_id,
            group_id=None,
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
