from typing import Literal, NotRequired, TypedDict, Union


class GoogleThought(TypedDict):
    """Google 模型的思考签名信息

    Attributes:
        thought_signature: 思考签名，用于验证模型输出
    """
    thought_signature: str


class ExtraContent(TypedDict):
    """额外内容，目前仅包含 Google 特定元数据

    Attributes:
        google: Google 模型的额外信息，如思考签名
    """
    google: GoogleThought


class ToolCallFunction(TypedDict):
    """工具调用的函数定义(流式传输中增量返回)

    Attributes:
        name: 函数名，仅在首个工具调用 chunk 出现
        arguments: JSON 格式的函数参数，流式传输中逐片段拼接
    """
    name: NotRequired[str]
    arguments: str


class ToolCall(TypedDict):
    """流式返回的工具调用片段

    Attributes:
        index: 工具调用的索引
        id: 工具调用的唯一标识，仅在首个工具调用 chunk 中出现
        type: 调用类型，固定为 "function"
        function: 函数名和参数的增量信息
        extra_content: Google 模型的额外元数据(如思考签名)，仅 Gemini 模型可能携带
    """
    index: NotRequired[int]             # DeepSeek 有，Gemini 无
    id: NotRequired[str]                # 只有第一个工具调用 chunk 带 id
    type: NotRequired[Literal["function"]]
    function: ToolCallFunction
    extra_content: NotRequired[ExtraContent]   # Gemini 可能包含 thought_signature


class Delta(TypedDict, total=False):
    """一次流式响应中携带的增量内容(所有字段均可选)

    Attributes:
        role: 角色，通常为 "assistant"，一般在首个 chunk 中
        content: 模型输出的纯文本增量
        tool_calls: 工具调用的增量信息列表
        extra_content: Google 模型的额外元数据(如思考签名)
    """
    role: str
    content: str
    tool_calls: list[ToolCall]
    extra_content: ExtraContent          # Gemini 文本流最后一个 chunk 可能包含


class Choice(TypedDict):
    """模型返回的一个候选结果

    Attributes:
        index: 候选结果的索引
        delta: 本次增量内容
        logprobs: 日志概率
        finish_reason: 终止原因，例如 "stop"、"tool_calls" 或 None,可能在最后一个 chunk 出现
    """
    index: int
    delta: Delta
    logprobs: NotRequired[None]                # DeepSeek 有，Gemini 无
    finish_reason: NotRequired[Union[str, None]]


class PromptTokensDetails(TypedDict):
    """提示词 token 的细节信息

    Attributes:
        cached_tokens: 命中缓存的 token 数量
    """
    cached_tokens: int


class Usage(TypedDict):
    """token 用量信息，通常只在最后一个 chunk 中出现

    Attributes:
        prompt_tokens: 提示词消耗的 token 数
        completion_tokens: 生成内容消耗的 token 数
        total_tokens: 总计 token 数
        prompt_tokens_details: 提示词 token 的细分信息
        prompt_cache_hit_tokens: 命中缓存的 token 数
        prompt_cache_miss_tokens: 未命中缓存的 token 数
    """
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: PromptTokensDetails
    prompt_cache_hit_tokens: int
    prompt_cache_miss_tokens: int


class ChatCompletionChunk(TypedDict):
    """一次流式对话补全的响应块

    Attributes:
        id: 本次请求的唯一标识
        object: 对象类型，固定为 "chat.completion.chunk"
        created: 创建时间戳(Unix 秒)
        model: 使用的模型名
        system_fingerprint: 系统指纹(DeepSeek 有)
        nonce: 随机数,Gemini 模型流式响应中携带
        choices: 模型返回的候选增量列表
        usage: token 用量信息，仅 DeepSeek 最后一个 chunk 携带
    """
    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    system_fingerprint: NotRequired[str]   # DeepSeek 有
    nonce: NotRequired[str]                # Gemini 有
    choices: list[Choice]
    usage: NotRequired[Usage]              # DeepSeek 最后一个 chunk 才有
    

class ChatCompletion(TypedDict):
    """一次性对话补全的完整响应

    Attributes:
        id: 请求唯一标识
        object: 对象类型，通常为 "chat.completion"
        created: 创建时间戳(Unix 秒)
        model: 模型名称
        choices: 候选回复列表
        usage: token 用量统计
        system_fingerprint: 系统指纹
        nonce: 随机数标识(Gemini 流式中常见，非流式偶尔携带)
    """
    id: str
    object: str                           # 非流式通常为 "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
    system_fingerprint: NotRequired[str]  # DeepSeek 提供
    nonce: NotRequired[str]               # Gemini 偶尔携带