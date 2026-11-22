from typing import Literal, NotRequired, Required, TypedDict

ChatRole = Literal["system", "user", "assistant", "tool"]
"""聊天消息角色"""


class GoogleThought(TypedDict):
    """Google 模型的思考签名信息

    Attributes:
        thought_signature: 思考签名,用于验证模型输出
    """

    thought_signature: str


class ExtraContent(TypedDict):
    """额外内容,目前仅包含 Google 特定元数据

    Attributes:
        google: Google 模型的额外信息,如思考签名
    """

    google: GoogleThought


class TextContentPart(TypedDict):
    """纯文本内容段"""

    type: Literal["text"]
    text: str


class ImageUrlDetail(TypedDict):
    """图片地址详情

    Attributes:
        url: 图片地址(http/https/data:base64/file URI)
        detail: 清晰度偏好 auto / low / high
    """

    url: str
    detail: NotRequired[str]


class ImageUrlContentPart(TypedDict):
    """图片内容段"""

    type: Literal["image_url"]
    image_url: ImageUrlDetail


class InputAudioData(TypedDict):
    """音频数据

    Attributes:
        data: base64 编码的音频数据
        format: 音频格式,如 wav / mp3
    """

    data: str
    format: str


class InputAudioContentPart(TypedDict):
    """音频内容段"""

    type: Literal["input_audio"]
    input_audio: InputAudioData


class VideoUrlDetail(TypedDict):
    """视频地址详情

    Attributes:
        url: 视频地址
    """

    url: str


class VideoUrlContentPart(TypedDict):
    """视频内容段"""

    type: Literal["video_url"]
    video_url: VideoUrlDetail


class FileDetail(TypedDict):
    """文件详情

    Attributes:
        url: 文件地址
        mime_type: MIME 类型
    """

    url: str
    mime_type: NotRequired[str]


class FileContentPart(TypedDict):
    """文件内容段"""

    type: Literal["file"]
    file: FileDetail


ChatContentPart = (
    TextContentPart
    | ImageUrlContentPart
    | InputAudioContentPart
    | VideoUrlContentPart
    | FileContentPart
)
"""多模态内容段"""

ChatContent = str | list[ChatContentPart]
"""消息 content:纯文本时为 str,多模态时为内容段列表"""


class FunctionCall(TypedDict):
    """完整(非流式)的函数调用信息

    Attributes:
        name: 函数名
        arguments: 完整 JSON 字符串形式的函数参数
    """

    name: str
    arguments: str


class ToolCallDict(TypedDict):
    """上下文中的一次完整工具调用(区别于流式增量片段)

    Attributes:
        id: 工具调用的唯一标识
        type: 调用类型,固定为 "function"
        function: 函数名和参数信息
        extra_content: Google 模型的额外元数据(如思考签名)
    """

    id: str
    type: Literal["function"]
    function: FunctionCall
    extra_content: NotRequired[ExtraContent]


class SystemMessage(TypedDict):
    """系统消息"""

    role: Literal["system"]
    content: ChatContent
    name: NotRequired[str]


class UserMessage(TypedDict):
    """用户消息"""

    role: Literal["user"]
    content: ChatContent
    name: NotRequired[str]


class AssistantMessage(TypedDict):
    """助手消息

    Attributes:
        content: 文本或多模态内容,仅有工具调用时可为空或缺省
        tool_calls: 模型请求调用的工具列表
        reasoning_content: 思考过程
        extra_content: Google 模型的额外元数据(如思考签名)
        refusal: 拒绝生成内容时的原因
    """

    role: Literal["assistant"]
    content: NotRequired[ChatContent | None]
    tool_calls: NotRequired[list[ToolCallDict]]
    reasoning_content: NotRequired[str]
    extra_content: NotRequired[ExtraContent]
    refusal: NotRequired[str | None]


class ToolMessage(TypedDict):
    """工具执行结果消息

    Attributes:
        content: 工具返回的文本或多模态内容
        tool_call_id: 对应的工具调用标识
        name: 工具名
    """

    role: Literal["tool"]
    content: ChatContent
    tool_call_id: str
    name: NotRequired[str]


ChatMessage = SystemMessage | UserMessage | AssistantMessage | ToolMessage
"""一条聊天消息(按角色区分的联合类型)"""


class ChatMessageDict(TypedDict, total=False):
    """动态构建/修改场景使用的宽松消息类型

    Context.add_* 与 MessageBuilder 会按需拼装字段,因此除 role 外全部可选。
    """

    role: Required[ChatRole]
    content: ChatContent
    name: str
    tool_calls: list[ToolCallDict]
    tool_call_id: str
    reasoning_content: str
    extra_content: ExtraContent
    refusal: str | None


ChatMessages = list[ChatMessageDict]
"""上下文消息列表(Context.messages / request.messages / messages 参数)"""
