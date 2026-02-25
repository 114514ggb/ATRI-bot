import datetime
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageSegmentType(Enum):
    AT = "at"              # @消息段
    CONTACT = "contact"    # 联系人消息段
    DICE = "dice"          # 骰子消息段
    FACE = "face"          # QQ表情消息段
    FILE = "file"          # 文件消息段
    FLASHTRANSFER = "flashtransfer"  # QQ闪传消息段
    FORWARD = "forward"    # 合并转发消息段
    IMAGE = "image"        # 图片消息段
    JSON = "json"          # JSON消息段
    LOCATION = "location"  # 位置消息段
    MARKDOWN = "markdown"  # Markdown消息段
    MFACE = "mface"        # 商城表情消息段
    MINIAPP = "miniapp"    # 小程序消息段
    MUSIC = "music"        # 音乐消息段
    NODE = "node"          # 合并转发消息节点
    ONLINEFILE = "onlinefile"  # 在线文件消息段
    POKE = "poke"          # 戳一戳消息段
    RECORD = "record"      # 语音消息段
    REPLY = "reply"        # 回复消息段
    RPS = "rps"            # 猜拳消息段
    TEXT = "text"          # 纯文本消息段
    VIDEO = "video"        # 视频消息段
    XML = "xml"            # XML消息段
    UNKNOWN = "unknown"    # 不支持的消息段


class MessageSegment(ABC):
    """基础消息段（抽象基类）"""
    
    __slots__ = ['type']
    
    def __init__(self, type: str):
        self.type = type
    
    @property
    @abstractmethod
    def data(self) -> Dict[str, Any]:
        """
        计算属性：返回消息段的用于发送的字典
        子类必须实现此方法
        """
        pass
    
    @abstractmethod
    def __str__(self) -> str:
        """
        返回简化的CQ码格式的字符串表示,用于给ai阅读
        子类必须实现此方法
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        序列化为OneBot标准格式的字典,用于发送消息用
        """
        return {
            "type": self.type,
            "data": self.data
        }


class TextSegment(MessageSegment):
    """文本"""
    __slots__ = ['text']
    
    def __init__(self, text: str):
        self.text = text
        super().__init__(MessageSegmentType.TEXT.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        return {"text": self.text}
    
    def __str__(self) -> str:
        return self.text


class AtSegment(MessageSegment):
    """@"""
    __slots__ = ['user_id']
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(MessageSegmentType.AT.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        return {"qq": self.user_id}
    
    def __str__(self) -> str:
        return f"[CQ:at,qq={self.user_id}]"


class FaceSegment(MessageSegment):
    """QQ 表情"""
    __slots__ = ['face_id']
    
    def __init__(self, face_id: str):
        self.face_id = face_id
        super().__init__(MessageSegmentType.FACE.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        return {"id": self.face_id}
    
    def __str__(self) -> str:
        return "[CQ:face]"


class ReplySegment(MessageSegment):
    """回复"""
    __slots__ = ['message_id']
    
    def __init__(self, message_id: str):
        self.message_id = message_id
        super().__init__(MessageSegmentType.REPLY.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        return {"id": self.message_id}
    
    def __str__(self) -> str:
        return f"[CQ:reply,id={self.message_id}]"


class JsonSegment(MessageSegment):
    """json"""
    __slots__ = ['json_data']
    
    def __init__(self, json_data: dict|str):
        if isinstance(json_data, dict):
            json_data = json.dumps(json_data, ensure_ascii=False)
        self.json_data = json_data
        super().__init__(MessageSegmentType.JSON.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        return {"data": self.json_data}
    
    def __str__(self) -> str:
        try:
            data = json.loads(self.json_data)
            detail_1 = data["meta"]["detail_1"]
            return f"[CQ:json,prompt={data.get('prompt')},title={detail_1.get('title')},desc={detail_1.get('desc')},url={detail_1.get('qqdocurl')}]"
        except Exception:
            return f"[CQ:json,data={str(self.json_data)[:1500]}]"


class ForwardSegment(MessageSegment):
    """合并转发消息"""
    __slots__ = ["id","content"]
    
    def __init__(self, id: str, content:list[dict]|None = None):
        self.id = id
        """合并转发ID"""
        self.content = content
        """消息内容 (OB11Message[])"""
        super().__init__(MessageSegmentType.FORWARD.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        data_dict= {"id": self.id}
        if self.content:
            data_dict["content"] = self.content
        
        return data_dict
    
    def __str__(self) -> str:
        if self.content:
            content_str = "".join(ChatMessage.from_chat_event(m).llm_formatted_message for m in self.content)
            return f"[CQ:转发消息,id={self.id},content={content_str[:5000]}]"
        return f"[CQ:forward,id={self.id}]"
    
    
class NodeSegment(MessageSegment):
    """合并转发消息节点"""
    
    __slots__ = ['id', 'user_id', 'uin', 'nickname', 'name', 'content', 'source', 'news', 'summary', 'prompt', 'time']
    
    def __init__(
        self,
        nickname: str,
        content: Any,
        id: str | None = None,
        user_id: str | None = None,
        uin: str | None = None,
        name: str | None = None,
        source: str | None = "高性能秘籍",
        news: list[dict] | None = None,
        summary: str | None = "点击即看",
        prompt: str | None = "果然是群聊天记录",
        time: str | None = None
    ):
        """初始化合并转发消息节点。
        
        Args:
            nickname: 发送者的昵称（必填）。
            content: 消息的具体内容，遵循OB11MessageMixType协议（必填）。
            id: 转发消息的唯一标识ID（可选）。
            user_id: 发送者的QQ号（可选）。
            uin: 发送者的QQ号，兼容go-cqhttp协议格式（可选）。
            name: 发送者的昵称，兼容go-cqhttp协议格式（可选）。
            source: 标题文本（可选）。
            news: 预览文本（可选）格式list[dict][{"text" : "文本"}]
            summary: 底下文本（可选）。
            prompt: 消息的提示信息（可选）。
            time: 消息发送的时间（可选）。
        """
        self.id = id
        self.user_id = user_id
        self.uin = uin
        self.nickname = nickname
        self.name = name
        self.content = content
        self.source = source
        self.summary = summary
        self.prompt = prompt
        self.time = time
        if news is None:
            self.news = [{"text" : "ATRI:晚上一个人偷偷看[图片]"}]
        super().__init__(MessageSegmentType.NODE.value)
    
    @property
    def data(self) -> Dict[str, Any]:
        """返回消息段的用于发送的字典。"""
        data_dict: Dict[str, Any] = {
            "nickname": self.nickname,
            "content": self.content
        }
        
        if self.id is not None:
            data_dict["id"] = self.id
        if self.user_id is not None:
            data_dict["user_id"] = self.user_id
        if self.uin is not None:
            data_dict["uin"] = self.uin
        if self.name is not None:
            data_dict["name"] = self.name
        if self.source is not None:
            data_dict["source"] = self.source
        if self.news is not None:
            data_dict["news"] = self.news
        if self.summary is not None:
            data_dict["summary"] = self.summary
        if self.prompt is not None:
            data_dict["prompt"] = self.prompt
        if self.time is not None:
            data_dict["time"] = self.time
        
        return data_dict
    
    def __str__(self) -> str:
        """返回简化的CQ码格式的字符串表示。"""
        return f"[CQ:node,content={str(self.content)[:4000]}]"


@dataclass(slots=True)
class File:
    """要发送的文件。

    Attributes:
        file: 包含协议前缀的文件路径、URL 或 Base64 编码字符串。
    """
    file: str
    """用于发送的文件,是文件路径、URL 或 Base64 编码其中一个"""

    @classmethod
    def from_local_path(cls, path: str) -> "File":
        """从本地路径创建 File 对象,自动添加file://前缀

        Args:
            path: 本地文件绝对路径，例如 "D:/a.jpg"。

        Returns:
            File: 包含正确前缀的 File 实例。
        """
        return cls(file="file://" + path)

    @classmethod
    def from_url(cls, url: str) -> "File":
        """从网络 URL 创建 File 对象，自动添加 https:// 前缀

        Args:
            url: URL 字符串，不包含 http:// 或 https://

        Returns:
            File: 包含正确前缀的 File 实例。
        """
        return cls(file="https://" + url)

    @classmethod
    def from_base64(cls, data: str) -> "File":
        """从 Base64 编码字符串创建 File 对象，自动添加 base64:// 前缀。

        Args:
            data: Base64 编码的字符串，例如 "iVBORw0KGgo..."。

        Returns:
            File: 包含正确前缀的 File 实例。
        """
        return cls(file="base64://" + data)

    @staticmethod
    def detect_type(file_str: str) -> str:
        """根据前缀判断文件字符串的类型。

        Args:
            file_str: 带有协议前缀的字符串。

        Returns:
            str: 类型名称，可能为 "local", "http", "https", "base64", "unknown"。
        """
        if file_str.startswith("file://"):   return "local"
        if file_str.startswith("http://"):   return "http"
        if file_str.startswith("https://"):  return "https"
        if file_str.startswith("base64://"): return "base64"
        return "unknown"


class FileMessageSegment(MessageSegment, ABC):
    """文件类消息基类，强制要求 file 字段，其余为可选元信息"""

    __slots__ = ['file', 'url', 'path', 'file_size', 'file_name']

    def __init__(
        self,
        type: str, #MessageSegmentType
        file: File,
        file_name: str | None = None,
        url: str | None = None,         # 接收时带过来的网络地址
        path: str | None = None,        # 接收时带过来的本地地址
        file_size: int = 0,
    ):
        self.file_name = file_name
        """文件名"""
        self.file = file
        """发送的文件"""
        self.url = url
        """文件的网络路径"""
        self.path = path
        """文件的本地绝对路径"""
        self.file_size = file_size
        """文件大小字节"""
        super().__init__(type)

    def get_path(self)->Path:
        """获取文件的路径,不会进行是否存在检测"""
        return Path(self.path)

    @classmethod
    def from_local_path(cls, file_path: str, **kwargs) -> "FileMessageSegment":
        """从本地路径构造"""
        return cls(file=File.from_local_path(file_path), **kwargs)

    @classmethod
    def from_url(cls, file_url: str, **kwargs) -> "FileMessageSegment":
        """从网络 URL 构造"""
        return cls(file=File.from_url(file_url), **kwargs)

    @classmethod
    def from_base64(cls, data: str, **kwargs) -> "FileMessageSegment":
        """从 Base64 字符串构造"""
        return cls(file=File.from_base64(data), **kwargs)

    @property
    def data(self) -> Dict[str, Any]:
        return {"file": self.file.file}

    @abstractmethod
    def __str__(self) -> str:
        pass


class ImageSegment(FileMessageSegment):
    """图片"""
    __slots__ = ["summary"]
    
    def __init__(
        self,
        file: File,
        file_name: str | None = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
        file_size: int = 0,
        summary: Optional[str] = None,
    ):
        super().__init__(MessageSegmentType.IMAGE.value, file, file_name, url, path, file_size)
        self.summary:str = summary
        """图片描述(可选)"""
    
    @property
    def data(self) -> Dict[str, Any]:
        data_dict = {"file": self.file.file}
        
        if self.summary:
            data_dict["summary"] = self.summary
        
        return data_dict
    
    def __str__(self) -> str:
        summary_part = f"summary={self.summary}," if self.summary else ""
        return f"[CQ:image,{summary_part}file={self.file_name},url={self.url}]"


class RecordSegment(FileMessageSegment):
    """语音"""
    __slots__ = []
    
    def __init__(
        self,
        file: File,
        file_name: str | None = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
        file_size: int = 0,
    ):
        super().__init__(MessageSegmentType.RECORD.value, file, file_name, url, path, file_size)
    
    def __str__(self) -> str:
        return f"[CQ:record,file={self.file_name}]"

class VideoSegment(FileMessageSegment):
    """视频"""
    __slots__ = ["thumb"]
    
    def __init__(
        self,
        file: File,
        file_name: str | None = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
        file_size: int = 0,
        thumb:str = None
    ):
        super().__init__(MessageSegmentType.VIDEO.value, file, file_name, url, path, file_size)
        self.thumb = thumb
        """视频缩略图(可选)"""
    
    @property
    def data(self) -> Dict[str, Any]:
        data_dict = {"file": self.file.file}
        
        if self.thumb:
            data_dict["thumb"] = self.thumb
        
        return data_dict
    
    def __str__(self) -> str:
        return f"[CQ:video,file={self.file_name}]"

class FileSegment(FileMessageSegment):
    """文件"""
    __slots__ = []
    
    def __init__(
        self,
        file: File,
        file_name: str | None = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
        file_size: int = 0,
    ):
        super().__init__(MessageSegmentType.FILE.value, file, file_name, url, path, file_size)
    
    @property
    def data(self) -> Dict[str, Any]:
        data_dict = {"file": self.file.file}
        
        if self.file_name:#可选的文件名
            data_dict["name"] = self.file_name
        
        return data_dict
    
    def __str__(self) -> str:
        return f"[CQ:file,file={self.file_name}]"
        
class UnknownSegment(MessageSegment):
    """兼容类"""
    __slots__ = ['_raw_type', '_raw_data']
    
    def __init__(self, type_str: str, data: Dict[str, Any]):
        self._raw_type = type_str
        self._raw_data = data
        super().__init__(type_str)
    
    @property
    def data(self) -> Dict[str, Any]:
        return self._raw_data
    
    def __str__(self) -> str:
        return f"[CQ:{self._raw_type},data:{str(self.data)[:1000]}]"


@dataclass(slots=True)
class ChatMessage:
    """接收的消息"""
    
    self_id: int 
    """接收账号"""
    user_id: int
    """发送的user"""
    group_id: Optional[int]
    """在的群号"""
    message_id: int
    """消息的唯一编码"""
    time: int 
    """时间戳秒级"""
    raw_message: str 
    """原始cq码文本消息"""
    primeval:dict
    """原始接收的data的dict"""
    llm_formatted_message: str = ""
    """重新处理过的短文本LLM友好的文本"""
    pure_text: str = ""
    """消息的文本部分"""
    segments: List[MessageSegment] = field(default_factory=list)
    """消息段"""
    sender_info: Dict[str, Any] = field(default_factory=dict)
    """user相关信息字典参考值
    {
        'user_id': 2631018780, # 发送者qq号
        'nickname': '除了摸鱼什么都做不到', # 账号名
        'card': '',  # 群名
        'role': 'owner' # 群角色
    }
    """

    @classmethod
    def from_chat_event(cls, event: Dict[str, Any]) -> "ChatMessage":
        """
        工厂方法：从接收到的 JSON 事件中实例化 ChatMessage
        """
        self_id = event.get('self_id', 0)
        user_id = event.get('user_id', 0)

        parsed_segments: List[MessageSegment] = []
        pure_text_parts: List[str] = []

        for seg in event.get('message', []):
            t = seg.get('type')
            d: Dict[str, Any] = seg.get('data', {})

            if t == MessageSegmentType.TEXT.value:
                text = d.get('text', '')
                parsed_segments.append(TextSegment(text))
                pure_text_parts.append(text)
            
            elif t == MessageSegmentType.IMAGE.value:
                file_str = d.get('url') or d.get('path')
                parsed_segments.append(ImageSegment(
                    file=File(file_str),
                    file_name=d.get('file'),
                    url=d.get('url'),
                    path=d.get('path'),
                    file_size=d.get('file_size', 0),
                    summary=d.get('summary')
                ))
            
            elif t == MessageSegmentType.REPLY.value:
                parsed_segments.append(ReplySegment(str(d.get('id', ''))))
            
            elif t == MessageSegmentType.AT.value:
                parsed_segments.append(AtSegment(int(d.get('qq', 0))))
            
            elif t == MessageSegmentType.FACE.value:
                parsed_segments.append(FaceSegment(str(d.get('id', ''))))
            
            elif t == MessageSegmentType.RECORD.value:
                file_str = d.get('url') or d.get('path')
                parsed_segments.append(RecordSegment(
                    file=File(file_str),
                    file_name=d.get('file'),
                    url=d.get('url'),
                    path=d.get('path'),
                    file_size=d.get('file_size', 0)
                ))
            
            elif t == MessageSegmentType.FORWARD.value:
                parsed_segments.append(ForwardSegment(id=d.get('id', ""), content=d.get('content')))
            
            elif t == MessageSegmentType.FILE.value:
                file_str = d.get('url') or d.get('path') or d.get('file', '')
                parsed_segments.append(FileSegment(
                    file=File(file_str),
                    file_name=d.get('file'),
                    url=d.get('url'),
                    path=d.get('path'),
                    file_size=d.get('file_size', 0)
                ))
            
            elif t == MessageSegmentType.VIDEO.value:
                file_str = d.get('url') or d.get('path')
                parsed_segments.append(VideoSegment(
                    file=File(file_str),
                    file_name=d.get('file'),
                    url=d.get('url'),
                    path=d.get('path'),
                    file_size=d.get('file_size', 0),
                    thumb=d.get('thumb')
                ))
            
            else:
                parsed_segments.append(UnknownSegment(t, d))
        
        chat_message = cls(
            self_id=self_id,
            user_id=user_id,
            group_id=event.get('group_id'),
            message_id=event.get('message_id', 0),
            time=event.get('time', int(time.time())),
            primeval=event,
            raw_message=event.get('raw_message', ''),
            llm_formatted_message="",
            pure_text="".join(pure_text_parts),
            segments=parsed_segments,
            sender_info=event.get('sender', {})
        )
        
        chat_message.llm_formatted_message = chat_message.format_for_llm()
        
        return chat_message
        
    @classmethod
    def from_not_chat_event(cls, event: Dict[str, Any]) -> "ChatMessage":
        """用于非聊天消息的初始化"""
        return cls(
            self_id=event.get('self_id', 0),
            user_id=event.get('user_id', 0),
            group_id=event.get('group_id'),
            message_id=event.get('message_id', 0),
            time=event.get('time', int(time.time())),
            primeval=event,
            raw_message=event.get('raw_message', ''),
            llm_formatted_message="",
            pure_text="",
            segments=[],
            sender_info=event.get('sender', {})
        )

    def to_list(self) -> List[Dict[str, Any]]:
        """
        将消息链转换为 JSON List 格式，用于原样发送整条消息
        """
        return [seg.to_dict() for seg in self.segments]
    
    def get_cq_code(self) -> str:
        """获取完整的CQ码字符串"""
        return "".join([str(seg) for seg in self.segments])

    def format_for_llm(self) -> str:
        """获取llm可读的字符串"""
        return (
            "<MESSAGE>"
            f"<qq_id>{self.user_id}</qq_id>"
            f"<nick_name>{self.sender_info.get('nickname')}</nick_name>"
            f"<time>{datetime.datetime.fromtimestamp(self.time).strftime('%Y-%m-%d %H:%M:%S')}</time>\n"
            f"<user_message>{self.get_cq_code()[:2000]}</user_message>"
            f"<message_id>{self.message_id}</message_id>"
            "</MESSAGE>"
        )

    
    def __str__(self):
        return self.llm_formatted_message


@dataclass(slots=True)
class SendMessage:
    """发送消息的基类"""
    
    segments: List[MessageSegment] = field(default_factory=list)
    """消息段列表"""
    
    def add_text(self, text: str) -> "SendMessage":
        """添加纯文本消息段"""
        self.segments.append(TextSegment(text))
        return self
    
    def add_image(
        self,
        file: str|File,
        file_name: Optional[str] = None,
        summary: Optional[str] = None
    ) -> "SendMessage":
        """
        添加图片消息段
        
        Args:
            file: 文件路径、URL、Base64字符串或 File 对象
            file_name: 文件名（可选）
            summary: 图片描述（可选）
        """
        if isinstance(file, str):
            if file.startswith(("file://", "http://", "https://", "base64://")):
                file_obj = File(file)
            elif file.startswith("/") or (len(file) > 1 and file[1] == ":"):
                file_obj = File.from_local_path(file)
            else:
                file_obj = File.from_local_path(file)
        else:
            file_obj = file
            
        self.segments.append(ImageSegment(
            file=file_obj,
            file_name=file_name,
            summary=summary
        ))
        return self
    
    def add_at(self, user_id: int) -> "SendMessage":
        """添加@某人的消息段"""
        self.segments.append(AtSegment(user_id))
        return self
    
    def add_reply(self, message_id: str|int) -> "SendMessage":
        """添加回复消息段,要添加的话要放在第一个"""
        self.segments.append(ReplySegment(message_id))
        return self
    
    def add_face(self, face_id: str|int) -> "SendMessage":
        """添加QQ表情消息段"""
        self.segments.append(FaceSegment(face_id))
        return self
    
    def add_record(
        self,
        file: str|File,
        file_name: Optional[str] = None
    ) -> "SendMessage":
        """添加语音消息段"""
        if isinstance(file, str):
            if file.startswith(("file://", "http://", "https://", "base64://")):
                file_obj = File(file)
            else:
                file_obj = File.from_local_path(file)
        else:
            file_obj = file
            
        self.segments.append(RecordSegment(
            file=file_obj,
            file_name=file_name
        ))
        return self
    
    def add_video(
        self,
        file: str | File,
        file_name: Optional[str] = None,
        thumb: Optional[str] = None
    ) -> "SendMessage":
        """添加视频消息段"""
        if isinstance(file, str):
            if file.startswith(("file://", "http://", "https://", "base64://")):
                file_obj = File(file)
            else:
                file_obj = File.from_local_path(file)
        else:
            file_obj = file
            
        self.segments.append(VideoSegment(
            file=file_obj,
            file_name=file_name,
            thumb=thumb
        ))
        return self
    
    def add_file(
        self,
        file: str|File,
        file_name: Optional[str] = None
    ) -> "SendMessage":
        """添加文件消息段"""
        if isinstance(file, str):
            if file.startswith(("file://", "http://", "https://", "base64://")):
                file_obj = File(file)
            else:
                file_obj = File.from_local_path(file)
        else:
            file_obj = file
            
        self.segments.append(FileSegment(
            file=file_obj,
            file_name=file_name
        ))
        return self
    
    def add_json(self, json_data: str) -> "SendMessage":
        """添加JSON消息段"""
        self.segments.append(JsonSegment(json_data))
        return self
    
    def add_forward(self, id: str, content: Optional[List[Dict]] = None) -> "SendMessage":
        """
        添加合并转发消息段
        
        Args:
            id: 合并转发ID
            content: 消息内容列表，每个元素为符合 OneBot 标准的消息段字典（可选）
        
        Returns:
            Self, 用于链式调用
        """
        self.segments.append(ForwardSegment(id=id, content=content))
        return self
    
    def add_node(
        self,
        nickname: str,
        content: Any,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        uin: Optional[str] = None,
        name: Optional[str] = None,
        source: Optional[str] = None,
        news: Optional[List[Dict]] = None,
        summary: Optional[str] = None,
        prompt: Optional[str] = None,
        time: Optional[str] = None
    ) -> "SendMessage":
        """
        添加合并转发消息节点
        
        Args:
            nickname: 发送者的昵称（必填）
            content: 消息的具体内容，遵循 OneBot 消息段格式（必填）
            id: 转发消息的唯一标识ID（可选）
            user_id: 发送者的QQ号（可选）
            uin: 发送者的QQ号，兼容go-cqhttp协议格式（可选）
            name: 发送者的昵称，兼容go-cqhttp协议格式（可选）
            source: 标题文本（可选）
            news: 预览文本，格式为 [{"text": "文本"}]（可选）
            summary: 底部文本（可选）
            prompt: 消息的提示信息（可选）
            time: 消息发送的时间（可选）
        
        Returns:
            Self, 用于链式调用
        """
        node = NodeSegment(
            nickname=nickname,
            content=content,
            id=id,
            user_id=user_id,
            uin=uin,
            name=name,
            source=source,
            news=news,
            summary=summary,
            prompt=prompt,
            time=time
        )
        self.segments.append(node)
        return self
    
    def add_segment(self, segment: MessageSegment) -> "SendMessage":
        """直接添加自定义消息段"""
        self.segments.append(segment)
        return self
    
    def clear(self) -> "SendMessage":
        """清空所有消息段"""
        self.segments.clear()
        return self
    
    def is_empty(self) -> bool:
        """检查消息是否为空"""
        return len(self.segments) == 0
    
    @property
    def data(self) -> List[Dict[str, Any]]:
        """
        序列化为OneBot标准格式的消息列表
        """
        return [seg.to_dict() for seg in self.segments]
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.data, ensure_ascii=False)
    
    def __len__(self) -> int:
        """返回消息段数量"""
        return len(self.segments)
    
    def __str__(self) -> str:
        """返回CQ码格式字符串"""
        return "".join([str(seg) for seg in self.segments])
    
    def __bool__(self) -> bool:
        """判断消息是否非空"""
        return bool(self.segments)


@dataclass(slots=True, kw_only=True)
class GroupMessage(SendMessage):
    """群聊消息"""
    
    group_id: int
    """目标群号"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为发送群消息所需的完整字典"""
        return {
            "group_id": self.group_id,
            "message": self.data
        }
    
    def to_json(self) -> str:
        """转换为发送群消息的JSON字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass(slots=True, kw_only=True)
class PrivateMessage(SendMessage):
    """私聊消息"""
    
    user_id: int
    """目标用户QQ号"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为发送私聊消息所需的完整字典"""
        return {
            "user_id": self.user_id,
            "message": self.data
        }
    
    def to_json(self) -> str:
        """转换为发送私聊消息的JSON字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


