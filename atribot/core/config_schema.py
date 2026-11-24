"""配置段的 schema 定义（类型 + 默认值）

本模块的 dataclass 字段是配置默认值的唯一来源：`atri_config.CONFIG_DEFAULTS` 由
`ConfigSchema` 的字段自动生成，运行期再按它把缺失的段/键补进 `ConfigObject`（dict 子类）。
因此这里同时承担 IDE 补全/类型检查（`config.model.connect.supplier`）与默认值定义。

新增配置项：在对应 dataclass 上加字段（默认值写在这里），再给 `atriConfig` 补类型注解。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Union


class FreeForm(dict):
    """自由形态默认值：允许任意子键，未知键检查跳过，键值原样透传给下游"""


WhitelistIds = List[Union[int, str]]
"""白名单条目：QQ 号为整数，QQ 官方机器人可直接写 openid 字符串"""


@dataclass(slots=True)
class ModelEndpointConfig:
    """模型端点：供应商 + 模型名"""

    supplier: str = ""
    """供应商名（supplier_config.json 中的 ``name``）"""
    model_name: str = ""
    """模型名（供应商 ``models`` 的 key）"""


@dataclass(slots=True)
class ModelConnectConfig(ModelEndpointConfig):
    """主聊天模型端点"""

    user_global_context: bool = True
    """群聊内每人使用独立上下文；False 表示全群共享"""


@dataclass(slots=True)
class ModelMemoryConfig:
    """记忆系统使用的小模型"""

    summarize_model: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """记忆摘要模型"""


@dataclass(slots=True)
class ModelRAGConfig:
    """记忆检索（RAG）配置"""

    enable: bool = True
    dimensions: int = 1024
    """向量维度（需与嵌入模型一致）"""
    use_embedding_model: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """嵌入模型"""
    use_reranker_model: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """重排序模型"""
    vector_database: Dict[str, Any] = field(default_factory=FreeForm)
    """向量库扩展参数"""


@dataclass(slots=True)
class ModelConfig:
    """``model`` 段"""

    connect: ModelConnectConfig = field(default_factory=ModelConnectConfig)
    """主聊天模型"""
    group_chat: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """群聊模型（留空回退 ``connect``）"""
    private_chat: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """私聊模型（留空回退 ``connect``）"""
    chat_parameter: Dict[str, Any] = field(default_factory=FreeForm)
    """请求参数：键值原样并入请求体，空表示走内置默认参数"""
    detection_image: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """图片识别模型"""
    detection_audio: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """音频识别模型"""
    detection_video: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """视频识别模型"""
    tavily_search_API_key: str = ""
    standby_model: List[Dict[str, Any]] = field(default_factory=list)
    """备用模型列表，每项含 ``supplier`` / ``model_name``"""
    memory: ModelMemoryConfig = field(default_factory=ModelMemoryConfig)
    """记忆系统模型"""
    agency_Agent: ModelEndpointConfig = field(default_factory=ModelEndpointConfig)
    """子代理模型（留空回退 ``memory.summarize_model``）"""
    RAG: ModelRAGConfig = field(default_factory=ModelRAGConfig)
    """记忆检索配置"""


@dataclass(slots=True)
class AIChatConfig:
    """``ai_chat`` 段：人设与上下文窗口"""

    playRole: str = "none"
    """默认人设（character_setting 目录下的文件名）"""
    ai_max_record: int = 10
    """上下文保留的对话轮数"""
    group_max_record: int = 20
    """群消息缓存条数"""
    private_max_record: int = 20
    """私聊上下文轮数"""
    history_image_limit: int = 2
    """历史上下文发送的真实图片数量上限；支持图像的模型只接收这么多张，
    其余仅保留 CQ 占位；不支持图像的模型全部转文字描述（-1 不限制）"""
    history_audio_limit: int = 1
    """同上，音频"""
    history_video_limit: int = 1
    """同上，视频"""


@dataclass(slots=True)
class SandboxConfig:
    """``sand_box`` 段：LLM 代码执行沙盒"""

    type: str = "docker"
    """后端：docker / none（本机直执行）/ e2b"""
    image: str = "python:3.12-slim"
    """Docker 镜像名（仅 docker 后端生效）"""
    tool_prompts: Dict[str, str] = field(default_factory=FreeForm)
    """按工具名覆盖工具描述"""
    tools: Dict[str, bool] = field(default_factory=FreeForm)
    """按工具名显式启用/禁用"""


@dataclass(slots=True)
class DatabaseConfig:
    """``database`` 段：PostgreSQL 连接参数"""

    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "atri"


@dataclass(slots=True)
class WebPanelConfig:
    """``web_panel`` 段：Web 管理面板"""

    enable: bool = True
    host: str = "127.0.0.1"
    """监听地址（Docker 部署需改为 0.0.0.0）"""
    port: int = 5125
    access_token: str = ""
    """主令牌；留空回退环境变量 ATRI_PANEL_TOKEN"""
    session_ttl_hours: int = 4
    """登录会话有效期（1-24 小时）"""
    mask_secrets: bool = True
    """配置接口是否对密钥打码"""
    block_weak_token: bool = False
    """是否硬性拒绝弱主令牌登录"""
    db_console_readonly: bool = False
    """SQL 控制台是否只允许查询语句"""


@dataclass(slots=True)
class TTSConfig:
    """``tts`` 段：语音合成"""

    api_url: str = "http://127.0.0.1:9880"
    """GPT-SoVITS 接口地址"""
    emotions: Dict[str, Dict[str, Any]] = field(default_factory=FreeForm)
    """情感 → 参考音频参数；留空回退内置三情感"""


@dataclass(slots=True)
class ConfigSchema:
    """所有顶层配置段的默认值（`CONFIG_DEFAULTS` 的生成来源）"""

    root_user_id: int | None = None
    """Root 用户 QQ 号（无视名单限制）"""
    model: ModelConfig = field(default_factory=ModelConfig)
    ai_chat: AIChatConfig = field(default_factory=AIChatConfig)
    sand_box: SandboxConfig = field(default_factory=SandboxConfig)
    tool_presets: Dict[str, Any] = field(default_factory=FreeForm)
    """值为工具名列表，或 ``{"default": [...], "deferred": [...]}``"""
    group_white_list: WhitelistIds = field(default_factory=list)
    """接收消息处理的群白名单"""
    group_initiative_chat_white_list: WhitelistIds = field(default_factory=list)
    """允许主动发起对话的群"""
    group_information_extraction: WhitelistIds = field(default_factory=list)
    """自动提取话题的群"""
    private_chat_white_list: WhitelistIds = field(default_factory=list)
    """可触发 LLM 私聊的用户"""
    initiative_chat_keyword_trigger: List[str] | None = None
    """None 表示未配置（回退内置关键词），[] 表示关闭关键词触发"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    web_panel: WebPanelConfig = field(default_factory=WebPanelConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
