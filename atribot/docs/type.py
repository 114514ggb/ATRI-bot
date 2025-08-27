from dataclasses import dataclass, field
from enum import Enum
from typing import List, Union, Optional, Any

"""
能接收到的数据介绍
但是不会将接收到的json转换成object，一般会统一处理接受到的json
"""


#枚举类型
class EventType(Enum):
    META = 'meta_event'
    REQUEST = 'request'
    NOTICE = 'notice'
    MESSAGE = 'message'
    MESSAGE_SENT = 'message_sent'

class LifeCycleSubType(Enum):
    ENABLE = 'enable'
    DISABLE = 'disable'
    CONNECT = 'connect'

class GroupDecreaseSubType(Enum):
    LEAVE = 'leave'
    KICK = 'kick'
    KICK_ME = 'kick_me'
    DISBAND = 'disband'

#基类定义
@dataclass
class OneBotEvent:
    time: int
    self_id: int
    post_type: EventType = field(init=False)

@dataclass
class OB11BaseMetaEvent(OneBotEvent):
    post_type: EventType = EventType.META
    meta_event_type: str = field(init=False)

#元事件
@dataclass
class HeartbeatStatus:
    online: Optional[bool] = None
    good: bool

@dataclass
class OB11HeartbeatEvent(OB11BaseMetaEvent):
    meta_event_type: str = 'heartbeat'
    status: HeartbeatStatus
    interval: int

@dataclass
class OB11LifeCycleEvent(OB11BaseMetaEvent):
    meta_event_type: str = 'lifecycle'
    sub_type: LifeCycleSubType

#通知事件基类
@dataclass
class OB11BaseNoticeEvent(OneBotEvent):
    post_type: EventType = EventType.NOTICE

@dataclass
class OB11GroupNoticeEvent(OB11BaseNoticeEvent):
    group_id: int
    user_id: int

#具体通知事件
@dataclass
class OB11FriendAddNoticeEvent(OB11BaseNoticeEvent):
    notice_type: str = 'friend_add'
    user_id: int

@dataclass
class OB11FriendRecallNoticeEvent(OB11BaseNoticeEvent):
    notice_type: str = 'friend_recall'
    user_id: int
    message_id: int

@dataclass
class OB11GroupRecallNoticeEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_recall'
    operator_id: int
    message_id: int

@dataclass
class OB11GroupIncreaseEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_increase'
    operator_id: int
    sub_type: str  # 'approve' | 'invite'

@dataclass
class OB11GroupDecreaseEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_decrease'
    sub_type: GroupDecreaseSubType
    operator_id: int

@dataclass
class OB11GroupAdminNoticeEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_admin'
    sub_type: str  # 'set' | 'unset'

@dataclass
class OB11GroupBanEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_ban'
    operator_id: int
    duration: int
    sub_type: str  # 'ban' | 'lift_ban'

@dataclass
class GroupUploadFile:
    id: str
    name: str
    size: int
    busid: int

@dataclass
class OB11GroupUploadNoticeEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_upload'
    file: GroupUploadFile

@dataclass
class OB11GroupCardEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_card'
    card_new: str
    card_old: str

@dataclass
class OB11GroupNameEvent(OB11GroupNoticeEvent):
    notice_type: str = 'notify'
    sub_type: str = field(default='group_name', init=False)
    name_new: str

@dataclass
class OB11GroupTitleEvent(OB11GroupNoticeEvent):
    notice_type: str = 'notify'
    sub_type: str = field(default='title', init=False)
    title: str

@dataclass
class OB11GroupEssenceEvent(OB11GroupNoticeEvent):
    notice_type: str = 'essence'
    message_id: int
    sender_id: int
    operator_id: int
    sub_type: str  # 'add' | 'delete'

@dataclass
class MsgEmojiLike:
    emoji_id: str
    count: int

@dataclass
class OB11GroupMsgEmojiLikeEvent(OB11GroupNoticeEvent):
    notice_type: str = 'group_msg_emoji_like'
    message_id: int
    likes: List[MsgEmojiLike]

@dataclass
class OB11PokeEvent(OB11BaseNoticeEvent):
    notice_type: str = 'notify'
    sub_type: str = field(default='poke', init=False)
    target_id: int
    user_id: int

@dataclass
class OB11FriendPokeEvent(OB11PokeEvent):
    raw_info: Any
    sender_id: int

@dataclass
class OB11GroupPokeEvent(OB11PokeEvent):
    group_id: int
    raw_info: Any

@dataclass
class OB11ProfileLikeEvent(OB11BaseNoticeEvent):
    notice_type: str = 'notify'
    sub_type: str = field(default='profile_like', init=False)
    operator_id: int
    operator_nick: str
    times: int
    time: int

@dataclass
class OB11InputStatusEvent(OB11BaseNoticeEvent):
    notice_type: str = 'notify'
    sub_type: str = field(default='input_status', init=False)
    status_text: str
    event_type: int
    user_id: int
    group_id: Optional[int] = None

@dataclass
class BotOfflineEvent(OB11BaseNoticeEvent):
    notice_type: str = 'bot_offline'
    user_id: int
    tag: str
    message: str

#请求事件
@dataclass
class OB11FriendRequestEvent(OB11BaseNoticeEvent):
    post_type: EventType = EventType.REQUEST
    request_type: str = 'friend'
    user_id: int
    comment: str
    flag: str

@dataclass
class OB11GroupRequestEvent(OB11GroupNoticeEvent):
    post_type: EventType = EventType.REQUEST
    request_type: str = 'group'
    user_id: int
    comment: str
    flag: str
    sub_type: str

#消息事件
@dataclass
class OB11BaseMessageEvent(OneBotEvent):
    post_type: EventType = EventType.MESSAGE
    message_id: int
    user_id: int
    message: Union[str, List[Any]]
    raw_message: str

@dataclass
class PrivateSender:
    user_id: int
    nickname: str
    sex: str  # 'male' | 'female' | 'unknown'
    age: int

@dataclass
class OB11PrivateMessageEvent(OB11BaseMessageEvent):
    message_type: str = 'private'
    sub_type: str  # 'friend' | 'group' | 'other'
    sender: PrivateSender

@dataclass
class GroupSender:
    user_id: int
    nickname: str
    card: str
    role: str  # 'owner' | 'admin' | 'member'
    title: str
    level: str

@dataclass
class OB11GroupMessageEvent(OB11BaseMessageEvent):
    message_type: str = 'group'
    group_id: int
    anonymous: Optional[Any] = None
    sender: GroupSender

@dataclass
class OB11MessageSentEvent(OB11BaseMessageEvent):
    post_type: EventType = EventType.MESSAGE_SENT
    message_type: str  # 'private' | 'group'
    target_id: int