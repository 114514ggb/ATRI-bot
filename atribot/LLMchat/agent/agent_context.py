from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from atribot.common_utils.message_utils import count_estimate_tokens


@dataclass(slots=True)
class BaseMessageSegment(ABC):
    """AI 消息段基类

    消息段负责把自身转换成某个模型供应商可接收的字典
    默认实现使用 OpenAI Chat Completions 的 content part 风格

    Attributes:
        type: 消息段类型
    """

    type: str
    """消息段类型"""

    def __init__(self, type: str):
        """初始化消息段

        Args:
            type: 消息段类型
        """
        self.type = type

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """转换为模型 API 可接收的消息段字典

        Returns:
            当前消息段的模型 API 字典
        """


@dataclass(slots=True)
class BaseAgentMessage(ABC):
    """AI 消息基类

    Attributes:
        role: 消息角色
        content: 消息段列表
        tool_calls: 助手消息关联的工具调用列表
        tool_call_id: 工具返回消息关联的工具调用 ID
        name: 可选的消息发送者名称
    """

    role: Literal[
        "system",
        "user",
        "assistant",
        "tool"
    ]
    """消息角色"""
    content: list[BaseMessageSegment]
    """消息段列表"""
    tool_calls: list[dict[str, Any]] | None
    """助手消息关联的工具调用列表"""
    tool_call_id: str | None
    """工具返回消息关联的工具调用 ID"""
    name: str | None
    """可选的消息发送者名称"""

    def __init__(
        self,
        role: str,
        content: Iterable[BaseMessageSegment] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ):
        """初始化 AI 消息

        Args:
            role: 消息角色，例如 ``system``、``user``、``assistant`` 或 ``tool``
            content: 初始消息段集合
            tool_calls: 助手消息关联的工具调用列表
            tool_call_id: 工具返回消息关联的工具调用 ID
            name: 可选的消息发送者名称
        """
        self.role = role
        self.content = list(content or [])
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id
        self.name = name

    def add_segment(self, segment: BaseMessageSegment) -> "BaseAgentMessage":
        """向当前消息追加一个消息段

        Args:
            segment: 要追加的消息段

        Returns:
            当前消息对象，便于链式调用
        """
        self.content.append(segment)
        return self

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """转换为模型 API 可接收的消息字典

        Returns:
            当前消息的模型 API 字典
        """


@dataclass(slots=True)
class BaseAgentContext(ABC):
    """AI 上下文基类

    Attributes:
        messages: 上下文消息列表
        token: 当前上下文的 token 数
    """

    messages: list[BaseAgentMessage]
    """上下文消息列表"""
    token: int
    """当前上下文的 token 数"""

    def __init__(self, messages: Iterable[BaseAgentMessage] | None = None):
        """初始化上下文

        Args:
            messages: 初始上下文消息集合
        """
        self.messages = list(messages or [])
        self.token = 0

    def __len__(self) -> int:
        """返回上下文中的消息数量

        Returns:
            消息数量
        """
        return len(self.messages)

    def __iter__(self) -> Iterator[BaseAgentMessage]:
        """迭代上下文中的消息

        Returns:
            消息迭代器
        """
        return iter(self.messages)

    def __getitem__(self, index: int) -> BaseAgentMessage:
        """按索引获取上下文消息

        Args:
            index: 消息索引

        Returns:
            指定索引处的消息
        """
        return self.messages[index]

    def clear(self) -> None:
        """清空上下文消息"""
        self.messages.clear()

    @abstractmethod
    def add_message(self, message: BaseAgentMessage) -> BaseAgentMessage:
        """向上下文追加一条消息

        Args:
            message: 要追加的消息

        Returns:
            已追加的消息对象
        """

    @abstractmethod
    def get_messages(self) -> list[dict[str, Any]]:
        """获取模型 API 可用的消息列表

        Returns:
            模型 API 可用的 messages 列表
        """

    def to_dict(self) -> dict[str, Any]:
        """转换为包含 messages 的上下文字典

        Returns:
            包含 ``messages`` 字段的上下文字典
        """
        return {"messages": self.get_messages()}

    def get_token(self) -> int:
        """获取当前上下文的 token 数

        Returns:
            当前上下文的 token 数
        """
        return self.token

    def update_token(self, token: int | None = None) -> None:
        """更新当前上下文的 token 数
        如果提供了 token 值则直接更新，否则调用 message_utils 中的方法估算并更新

        Args:
            token: 可选的 token 数量
        """
        if token is not None:
            self.token = token
        else:
            self.token = count_estimate_tokens(self.get_messages())


@dataclass(slots=True)
class OpenAITextSegment(BaseMessageSegment):
    """OpenAI text 消息段

    Attributes:
        text: 文本内容
    """

    text: str
    """文本内容"""

    def __init__(self, text: str):
        """初始化文本消息段

        Args:
            text: 文本内容
        """
        BaseMessageSegment.__init__(self, "text")
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI text content part

        Returns:
            OpenAI text 消息段字典
        """
        return {"type": self.type, "text": self.text}


@dataclass(slots=True)
class OpenAIImageUrlSegment(BaseMessageSegment):
    """OpenAI image_url 消息段

    Attributes:
        url: 图片 URL
        detail: 可选的图片细节级别
    """

    url: str
    """图片 URL"""
    detail: str | None
    """可选的图片细节级别"""

    def __init__(self, url: str, detail: str | None = None):
        """初始化图片 URL 消息段

        Args:
            url: 图片 URL,或带有data:image/jpeg;base64,的开头的base64编码
            detail: 可选的图片细节级别
        """
        BaseMessageSegment.__init__(self, "image_url")
        self.url = url
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI image_url content part

        Returns:
            OpenAI image_url 消息段字典
        """
        image_url = {"url": self.url}
        if self.detail:
            image_url["detail"] = self.detail
        return {"type": self.type, "image_url": image_url}


@dataclass(slots=True)
class OpenAIAudioUrlSegment(BaseMessageSegment):
    """audio_url 消息段

    Attributes:
        url: 音频 URL
    """

    url: str
    """音频 URL"""

    def __init__(self, url: str):
        """初始化音频 URL 消息段

        Args:
            url: 音频 URL
        """
        BaseMessageSegment.__init__(self, "audio_url")
        self.url = url

    def to_dict(self) -> dict[str, Any]:
        """转换为 audio_url content part

        Returns:
            audio_url 消息段字典
        """
        return {"type": self.type, "audio_url": {"url": self.url}}


@dataclass(slots=True)
class OpenAIInputAudioSegment(BaseMessageSegment):
    """OpenAI input_audio 消息段，用于 base64 音频

    Attributes:
        data: base64 编码的音频数据
        format: 音频格式
    """

    data: str
    """base64 编码的音频数据"""
    format: str
    """音频格式"""

    def __init__(self, data: str, format: str = "wav"):
        """初始化输入音频消息段

        Args:
            data: base64 编码的音频数据
            format: 音频格式，默认 ``wav``
        """
        BaseMessageSegment.__init__(self, "input_audio")
        self.data = data
        self.format = format

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI input_audio content part

        Returns:
            OpenAI input_audio 消息段字典
        """
        return {"type": self.type, "input_audio": {"data": self.data, "format": self.format}}


@dataclass(slots=True)
class OpenAIVideoUrlSegment(BaseMessageSegment):
    """video_url 消息段

    Attributes:
        url: 视频 URL
    """

    url: str
    """视频 URL"""

    def __init__(self, url: str):
        """初始化视频 URL 消息段

        Args:
            url: 视频 URL
        """
        BaseMessageSegment.__init__(self, "video_url")
        self.url = url

    def to_dict(self) -> dict[str, Any]:
        """转换为 video_url content part

        Returns:
            video_url 消息段字典
        """
        return {"type": self.type, "video_url": {"url": self.url}}


@dataclass(slots=True)
class OpenAIRawSegment(BaseMessageSegment):
    """未内置适配的原始消息段

    Attributes:
        data: 原始消息段字典
    """

    data: dict[str, Any]
    """原始消息段字典"""

    def __init__(self, data: dict[str, Any]):
        """初始化原始消息段

        Args:
            data: 原始消息段字典
        """
        BaseMessageSegment.__init__(self, str(data.get("type", "unknown")))
        self.data = dict(data)

    def to_dict(self) -> dict[str, Any]:
        """返回原始消息段字典副本

        Returns:
            原始消息段字典的深拷贝
        """
        return deepcopy(self.data)


OpenAIContentLike = str | dict[str, Any] | BaseMessageSegment | Iterable[str | dict[str, Any] | BaseMessageSegment]


@dataclass(slots=True)
class OpenAIMessage(BaseAgentMessage):
    """OpenAI 规范消息

    支持把字符串、消息段字典或消息段对象统一转换为 OpenAI content
    """

    def __init__(
        self,
        role: str,
        content: OpenAIContentLike | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ):
        """初始化 OpenAI 消息

        Args:
            role: 消息角色，例如 ``system``、``user``、``assistant`` 或 ``tool``
            content: 消息内容，可以是字符串、消息段、消息段字典或它们的可迭代集合
            tool_calls: 助手消息关联的工具调用列表
            tool_call_id: 工具返回消息关联的工具调用 ID
            name: 可选的消息发送者名称
        """
        BaseAgentMessage.__init__(
            self,
            role=role,
            content=self._coerce_content(content),
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIMessage:
        """从 OpenAI message 字典构造消息对象

        Args:
            data: OpenAI message 字典

        Returns:
            构造出的 OpenAI 消息对象
        """
        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
        )

    @staticmethod
    def _coerce_content(content: OpenAIContentLike | None) -> list[BaseMessageSegment]:
        """把不同形式的 content 统一转换为消息段列表

        Args:
            content: 待转换的消息内容

        Returns:
            转换后的消息段列表
        """
        if content is None:
            return []
        if isinstance(content, str):
            return [OpenAITextSegment(content)]
        if isinstance(content, BaseMessageSegment):
            return [content]
        if isinstance(content, dict):
            return [OpenAIMessage._segment_from_dict(content)]
        return [OpenAIMessage._coerce_segment(item) for item in content]

    @staticmethod
    def _coerce_segment(item: str | dict[str, Any] | BaseMessageSegment) -> BaseMessageSegment:
        """把单个 content 项转换为消息段

        Args:
            item: 字符串、消息段字典或消息段对象

        Returns:
            转换后的消息段对象
        """
        if isinstance(item, BaseMessageSegment):
            return item
        if isinstance(item, str):
            return OpenAITextSegment(item)
        return OpenAIMessage._segment_from_dict(item)

    @staticmethod
    def _segment_from_dict(data: dict[str, Any]) -> BaseMessageSegment:
        """从消息段字典构造对应的消息段对象

        Args:
            data: OpenAI content part 字典

        Returns:
            对应类型的消息段对象；未知类型会返回原始消息段
        """
        segment_type = data.get("type")
        if segment_type == "text":
            return OpenAITextSegment(data.get("text", ""))
        if segment_type == "image_url":
            image_url = data.get("image_url", {})
            if isinstance(image_url, str):
                return OpenAIImageUrlSegment(image_url)
            return OpenAIImageUrlSegment(image_url.get("url", "")), image_url.get("detail")
        if segment_type == "audio_url":
            audio_url = data.get("audio_url", {})
            if isinstance(audio_url, str):
                return OpenAIAudioUrlSegment(audio_url)
            return OpenAIAudioUrlSegment(audio_url.get("url", ""))
        if segment_type == "input_audio":
            input_audio = data.get("input_audio", {})
            return OpenAIInputAudioSegment(input_audio.get("data", ""), input_audio.get("format", "wav"))
        if segment_type == "video_url":
            video_url = data.get("video_url", {})
            if isinstance(video_url, str):
                return OpenAIVideoUrlSegment(video_url)
            return OpenAIVideoUrlSegment(video_url.get("url", ""))
        return OpenAIRawSegment(data)

    def add_text(self, text: str) -> OpenAIMessage:
        """追加文本消息段

        Args:
            text: 文本内容

        Returns:
            当前消息对象，便于链式调用
        """
        return self.add_segment(OpenAITextSegment(text))

    def add_image_url(self, url: str, detail: str | None = None) -> OpenAIMessage:
        """追加图片 URL 消息段

        Args:
            url: 图片 URL
            detail: 可选的图片细节级别

        Returns:
            当前消息对象，便于链式调用
        """
        return self.add_segment(OpenAIImageUrlSegment(url, detail))

    def add_audio_url(self, url: str) -> OpenAIMessage:
        """追加音频 URL 消息段

        Args:
            url: 音频 URL

        Returns:
            当前消息对象，便于链式调用
        """
        return self.add_segment(OpenAIAudioUrlSegment(url))

    def add_input_audio(self, data: str, format: str = "wav") -> OpenAIMessage:
        """追加输入音频消息段

        Args:
            data: base64 编码的音频数据
            format: 音频格式，默认 ``wav``

        Returns:
            当前消息对象，便于链式调用
        """
        return self.add_segment(OpenAIInputAudioSegment(data, format))

    def add_video_url(self, url: str) -> OpenAIMessage:
        """追加视频 URL 消息段

        Args:
            url: 视频 URL

        Returns:
            当前消息对象，便于链式调用
        """
        return self.add_segment(OpenAIVideoUrlSegment(url))

    def add_segment(self, segment: BaseMessageSegment) -> OpenAIMessage:
        """向当前 OpenAI 消息追加一个消息段

        Args:
            segment: 要追加的消息段

        Returns:
            当前消息对象，便于链式调用
        """
        BaseAgentMessage.add_segment(self, segment)
        return self

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI message 字典

        Returns:
            OpenAI Chat Completions 兼容的消息字典
        """
        message: dict[str, Any] = {"role": self.role}

        if self.name:
            message["name"] = self.name
        if self.tool_call_id:
            message["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls

        if self.content:
            message["content"] = self._content_to_openai()
        elif not self.tool_calls:
            message["content"] = ""

        return message

    def _content_to_openai(self) -> str | list[dict[str, Any]]:
        """把消息段列表转换为 OpenAI content 字段

        仅包含单个文本段时返回字符串，以兼容最常见的 OpenAI 消息格式

        Returns:
            OpenAI message 的 content 字段值
        """
        if len(self.content) == 1 and isinstance(self.content[0], OpenAITextSegment):
            return self.content[0].text
        return [segment.to_dict() for segment in self.content]


@dataclass(slots=True)
class OpenAIAgentContext(BaseAgentContext):
    """OpenAI 规范上下文"""

    def __init__(self, messages: Iterable[OpenAIMessage | dict[str, Any]] | None = None):
        """初始化 OpenAI 上下文

        Args:
            messages: 初始消息集合，可以包含 OpenAIMessage 或 OpenAI message 字典
        """
        BaseAgentContext.__init__(self)
        if messages:
            self.extend(messages)

    def add_message(
        self,
        message: OpenAIMessage | dict[str, Any] | None = None,
        *,
        role: str = "user",
        content: OpenAIContentLike | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ) -> OpenAIMessage:
        """向上下文追加一条消息，并返回消息对象

        Args:
            message: 已构造的 OpenAI 消息或 OpenAI message 字典
            role: 当 ``message`` 为空时使用的消息角色
            content: 当 ``message`` 为空时使用的消息内容
            tool_calls: 当 ``message`` 为空时使用的工具调用列表
            tool_call_id: 当 ``message`` 为空时使用的工具调用 ID
            name: 当 ``message`` 为空时使用的消息发送者名称

        Returns:
            已追加的 OpenAI 消息对象
        """
        if message is None:
            message = OpenAIMessage(role, content, tool_calls=tool_calls, tool_call_id=tool_call_id, name=name)
        elif isinstance(message, dict):
            message = OpenAIMessage.from_dict(message)

        self.messages.append(message)
        return message

    def extend(self, messages: Iterable[OpenAIMessage | dict[str, Any]]) -> None:
        """批量追加消息

        Args:
            messages: 要追加的 OpenAI 消息或 OpenAI message 字典集合
        """
        for message in messages:
            self.add_message(message)

    def get_messages(self) -> list[dict[str, Any]]:
        """获取 OpenAI API 可用的 messages 列表

        Returns:
            OpenAI message 字典列表
        """
        return [message.to_dict() for message in self.messages]

    def add_user_message(self, content: OpenAIContentLike) -> OpenAIMessage:
        """追加用户消息

        Args:
            content: 用户消息内容

        Returns:
            已追加的用户消息对象
        """
        return self.add_message(role="user", content=content)

    def add_assistant_message(
        self,
        content: OpenAIContentLike | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> OpenAIMessage:
        """追加助手消息

        Args:
            content: 助手消息内容
            tool_calls: 助手消息关联的工具调用列表

        Returns:
            已追加的助手消息对象
        """
        return self.add_message(role="assistant", content=content, tool_calls=tool_calls)

    def add_system_message(self, content: OpenAIContentLike) -> OpenAIMessage:
        """追加系统消息

        Args:
            content: 系统消息内容

        Returns:
            已追加的系统消息对象
        """
        return self.add_message(role="system", content=content)

    def add_tool_message(self, tool_call_id: str, content: OpenAIContentLike, name: str | None = None) -> OpenAIMessage:
        """追加工具返回消息

        Args:
            tool_call_id: 关联的工具调用 ID
            content: 工具返回消息内容
            name: 可选的工具名称

        Returns:
            已追加的工具消息对象
        """
        return self.add_message(role="tool", content=content, tool_call_id=tool_call_id, name=name)


AgentContext = OpenAIAgentContext
AgentMessage = OpenAIMessage
TextSegment = OpenAITextSegment
ImageUrlSegment = OpenAIImageUrlSegment
AudioUrlSegment = OpenAIAudioUrlSegment
InputAudioSegment = OpenAIInputAudioSegment
VideoUrlSegment = OpenAIVideoUrlSegment
RawSegment = OpenAIRawSegment


__all__ = [
    "AgentContext",
    "AgentMessage",
    "AudioUrlSegment",
    "BaseAgentContext",
    "BaseAgentMessage",
    "BaseMessageSegment",
    "ImageUrlSegment",
    "InputAudioSegment",
    "OpenAIAgentContext",
    "OpenAIAudioUrlSegment",
    "OpenAIImageUrlSegment",
    "OpenAIInputAudioSegment",
    "OpenAIRawSegment",
    "OpenAITextSegment",
    "OpenAIVideoUrlSegment",
    "RawSegment",
    "TextSegment",
    "VideoUrlSegment",
]
