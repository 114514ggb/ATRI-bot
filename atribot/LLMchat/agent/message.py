from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


class MessageSegment(ABC):
    """消息段基类"""
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """将消息段转换为 OpenAI 等兼容平台的字典格式

        Returns:
            Dict[str, Any]: 消息段字典格式
        """
        pass


@dataclass(slots=True)
class TextSegment(MessageSegment):
    """纯文本消息段"""
    text: str
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_dict = {"type": "text", "text": self.text}

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class ImageURLSegment(MessageSegment):
    """图片 URL 消息段"""
    url: str
    detail: str = "auto"
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_dict = {
            "type": "image_url",
            "image_url": {"url": self.url, "detail": self.detail}
        }

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class ImageBase64Segment(MessageSegment):
    """图片 Base64 消息段"""
    data: str
    mime: str = "image/png"
    detail: str = "auto"
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_dict = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{self.mime};base64,{self.data}",
                "detail": self.detail
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class AudioSegment(MessageSegment):
    """音频输入消息段"""
    data: str
    fmt: str = "wav"
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_dict = {
            "type": "input_audio",
            "input_audio": {"data": self.data, "format": self.fmt}
        }

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class VideoURLSegment(MessageSegment):
    """视频 URL 消息段"""
    url: str
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_dict = {"type": "video_url", "video_url": {"url": self.url}}

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class VideoBase64Segment(MessageSegment):
    """视频 Base64 消息段"""
    data: str
    mime: str = "video/mp4"
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_dict = {
            "type": "video_url",
            "video_url": {"url": f"data:{self.mime};base64,{self.data}"}
        }

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class FileSegment(MessageSegment):
    """文件消息段"""
    url: str
    mime: str = ""
    _cached_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        res: Dict[str, Any] = {"type": "file", "file": {"url": self.url}}
        if self.mime:
            res["file"]["mime_type"] = self.mime
        self._cached_dict = res

    def to_dict(self) -> Dict[str, Any]:
        return self._cached_dict


@dataclass(slots=True)
class BaseMessage(ABC):
    """消息实体基类"""
    role: Literal["system", "user", "assistant", "tool"]
    
    @abstractmethod
    def to_openai_dict(self) -> Dict[str, Any]:
        """将消息转换为 OpenAI 等兼容平台的字典格式

        Returns:
            Dict[str, Any]: 消息字典格式
        """
        pass


@dataclass(slots=True)
class SystemMessage(BaseMessage):
    """系统消息实体"""
    role: Literal["system"] = "system"
    content: str = ""
    _cached_openai_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        self._cached_openai_dict = {"role": self.role, "content": self.content}

    def to_openai_dict(self) -> Dict[str, Any]:
        return self._cached_openai_dict


@dataclass(slots=True)
class UserMessage(BaseMessage):
    """用户消息实体"""
    role: Literal["user"] = "user"
    content: str | List[MessageSegment] = ""
    _cached_openai_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        if isinstance(self.content, str):
            self._cached_openai_dict = {"role": self.role, "content": self.content}
        else:
            self._cached_openai_dict = {
                "role": self.role,
                "content": [seg.to_dict() for seg in self.content]
            }

    def to_openai_dict(self) -> Dict[str, Any]:
        return self._cached_openai_dict


@dataclass(slots=True)
class AssistantMessage(BaseMessage):
    """助手消息实体，支持思考内容及工具调用"""
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    extra_content: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    _cached_openai_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        res: Dict[str, Any] = {"role": self.role}
        if self.content is not None:
            res["content"] = self.content
        if self.reasoning_content is not None:
            res["reasoning_content"] = self.reasoning_content
        if self.extra_content is not None:
            res["extra_content"] = self.extra_content
        if self.tool_calls is not None:
            res["tool_calls"] = self.tool_calls
        self._cached_openai_dict = res

    def to_openai_dict(self) -> Dict[str, Any]:
        return self._cached_openai_dict


@dataclass(slots=True)
class ToolMessage(BaseMessage):
    """工具消息实体"""
    tool_call_id: str = field(kw_only=True) 
    name: str = ""
    role: Literal["tool"] = "tool"
    content: str | List[MessageSegment] = ""
    _cached_openai_dict: Dict[str, Any] = field(init=False)

    def __post_init__(self):
        res: Dict[str, Any] = {
            "role": self.role,
            "tool_call_id": self.tool_call_id,
        }
        if self.name:
            res["name"] = self.name
        if isinstance(self.content, str):
            res["content"] = self.content
        else:
            res["content"] = [seg.to_dict() for seg in self.content]
        self._cached_openai_dict = res

    def to_openai_dict(self) -> Dict[str, Any]:
        return self._cached_openai_dict
