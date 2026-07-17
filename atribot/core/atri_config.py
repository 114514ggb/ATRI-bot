import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Union


class ConfigObject(dict):
    """将字典转换为支持点操作访问的对象

    该类继承自 dict 允许通过属性访问（.）来读取、设置和删除字典中的项
    如果值是嵌套字典，它也会被递归地转换为 ConfigObject
    """

    def __init__(self, data: Mapping[str, Any] | None = None):
        """初始化 ConfigObject 实例

        Args:
            data (Mapping[str, Any] | None): 初始数据字典默认为 None
        """
        super().__init__()
        if data:
            for key, value in data.items():
                self[key] = ConfigObject(value) if isinstance(value, dict) else value

    def __getattr__(self, name: str) -> Any:
        """获取属性

        Args:
            name (str): 属性名称

        Returns:
            Any: 对应的配置项值

        Raises:
            AttributeError: 如果配置项不存在
        """
        try:
            return self[name]
        except KeyError as exception:
            raise AttributeError(f"配置项 '{name}' 不存在") from exception

    def __setattr__(self, name: str, value: Any) -> None:
        """设置属性

        Args:
            name (str): 属性名称
            value (Any): 要设置的值，如果是字典则会被转换为 ConfigObject
        """
        self[name] = ConfigObject(value) if isinstance(value, dict) else value

    def __delattr__(self, name: str) -> None:
        """删除属性

        Args:
            name (str): 属性名称

        Raises:
            AttributeError: 如果配置项不存在
        """
        try:
            del self[name]
        except KeyError as exception:
            raise AttributeError(f"配置项 '{name}' 不存在") from exception


@dataclass(slots=True)
class FilePathConfig:
    """路径配置:统一管理项目根目录、document 根目录和派生路径

    该类负责解析并提供项目中各类资源的绝对路径

    Attributes:
        project_root (Path): 项目根目录的绝对路径
        document_root (Path): document 根目录的绝对路径
        commands (Path): 指令目录的绝对路径
        chat_manager (Path): 角色设定目录的绝对路径
        supplier_config_path (Path): 供应商配置文件路径
        tool_calls (Path): LLM使用的本地工具函数导入文件夹路径
        mcp_config (Path): MCP 配置文件路径
        agent_skills (Path): Agent 技能目录的绝对路径
        emoji (Path): 表情包目录的绝对路径
        audio (Path): 音频目录的绝对路径
        file (Path): 文件目录的绝对路径
        img (Path): 图片目录的绝对路径
        video (Path): 视频目录的绝对路径
        temp (Path): 临时目录的绝对路径
        root_relative (Dict[str, Path]): 基于 project_root 的其他相对路径映射
        document_relative (Dict[str, Path]): 基于 document_root 的其他相对路径映射
    """

    project_root: Path
    """项目根目录的绝对路径"""
    document_root: Path
    """document 根目录的绝对路径"""
    commands: Path
    """指令目录的绝对路径"""
    chat_manager: Path
    """角色设定目录的绝对路径"""
    supplier_config_path: Path
    """供应商配置文件路径"""
    tool_calls:Path
    """LLM使用的本地工具函数导入文件夹路径"""
    mcp_config: Path
    """MCP 配置文件路径"""
    agent_skills: Path
    """Agent 技能目录的绝对路径"""
    emoji: Path
    """表情包目录的绝对路径"""
    audio: Path
    """音频目录的绝对路径"""
    file: Path
    """文件目录的绝对路径"""
    img: Path
    """图片目录的绝对路径"""
    video: Path
    """视频目录的绝对路径"""
    temp: Path
    """临时目录的绝对路径"""
    root_relative: Dict[str, Path]
    """基于 project_root 的其他相对路径映射"""
    document_relative: Dict[str, Path]
    """基于 document_root 的其他相对路径映射"""

    @staticmethod
    def _to_absolute(base: Path, target: str) -> Path:
        """解析目标路径为绝对路径

        Args:
            base (Path): 基准路径
            target (str): 目标相对或绝对路径

        Returns:
            Path: 解析后的绝对路径对象
        """
        path = Path(target)
        if not path.is_absolute():
            path = base / path
        return path.resolve()

    @staticmethod
    def _normalize(path: Path, *, expect_file: bool = False) -> Path:
        """标准化路径

        Args:
            path (Path): 路径对象
            expect_file (bool): 是否按文件路径处理，若为 True 仅确保父目录存在

        Returns:
            Path: 路径对象
        """
        target_directory = path.parent if expect_file else path
        target_directory.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        project_root: Path,
    ) -> "FilePathConfig":
        """从字典数据中初始化 FilePathConfig 实例

        Args:
            data (Mapping[str, Any]): 包含路径映射的原始配置字典
            project_root (Path): 项目根目录

        Returns:
            FilePathConfig: 初始化的路径配置对象
        """
        file_path_config = dict(data)

        resolve_paths: bool = file_path_config.get("resolve_paths", True)
        create_dirs: bool = file_path_config.get("create_dirs", True)

        if resolve_paths:
            def to_absolute(base: Path, target: str) -> Path:
                path = Path(target)
                if not path.is_absolute():
                    path = base / path
                return path.resolve()
        else:
            def to_absolute(base: Path, target: str) -> Path:
                path = Path(target)
                if not path.is_absolute():
                    path = base / path
                return path

        if create_dirs:
            def normalize(path: Path, *, expect_file: bool = False) -> Path:
                target_directory = path.parent if expect_file else path
                try:
                    target_directory.mkdir(parents=True, exist_ok=True)
                except OSError:
                    pass
                return path
        else:
            def normalize(path: Path, *, expect_file: bool = False) -> Path:
                return path

        document_raw = file_path_config.get("document_root")
        document_root = Path(document_raw) if document_raw else to_absolute(project_root, "document")
        
        if emoji_raw := file_path_config.get("emoji"):
            emoji_path = Path(emoji_raw)
        else:
            emoji_path = project_root / "document/img/emojis"

        root_relative: Dict[str, str] = {
            "commands": "atribot/commands",
            "chat_manager": "atribot/LLMchat/character_setting",
            "supplier_config_path": "assets/supplier_config.json",
            "tool_calls": "atribot/LLMchat/tools",
            "mcp_config": "atribot/LLMchat/MCP/mcp_server.json",
            "agent_skills": "atribot/LLMchat/skills/agent_skills",
        }
        root_relative.update(file_path_config.get("relative_to_root", {}))

        document_relative: Dict[str, str] = {
            "audio": "audio",
            "file": "file",
            "img": "img",
            "video": "video",
            "temp": "temp",
        }
        document_relative.update(file_path_config.get("relative_to_document", {}))

        resolved_root = {
            name: normalize(
                to_absolute(project_root, relative_path),
                expect_file=name in {"supplier_config_path", "mcp_config"},
            )
            for name, relative_path in root_relative.items()
        }
        resolved_document = {
            name: normalize(to_absolute(document_root, relative_path))
            for name, relative_path in document_relative.items()
        }

        return cls(
            project_root=normalize(project_root),
            document_root=normalize(document_root),
            commands=resolved_root.get("commands", Path()),
            chat_manager=resolved_root.get("chat_manager", Path()),
            supplier_config_path=resolved_root.get("supplier_config_path", Path()),
            mcp_config=resolved_root.get("mcp_config", Path()),
            agent_skills=resolved_root.get("agent_skills", Path()),
            tool_calls=resolved_root.get("tool_calls", Path()),
            emoji=normalize(emoji_path),
            audio=resolved_document.get("audio", Path()),
            file=resolved_document.get("file", Path()),
            img=resolved_document.get("img", Path()),
            video=resolved_document.get("video", Path()),
            temp=resolved_document.get("temp", Path()),
            root_relative=resolved_root,
            document_relative=resolved_document,
        )

    def resolve_from_root(self, relative_path: str) -> Path:
        """基于 `project_root` 解析任意相对路径并返回绝对路径 Path 对象

        Args:
            relative_path (str): 相对项目根目录的路径

        Returns:
            Path: 解析后的绝对路径对象
        """
        path = self._to_absolute(self.project_root, relative_path)
        return self._normalize(path, expect_file=path.suffix != "")

    def resolve_from_document(self, relative_path: str) -> Path:
        """基于 `document_root` 解析任意相对路径并返回绝对路径 Path 对象

        Args:
            relative_path (str): 相对 document 目录的路径

        Returns:
            Path: 解析后的绝对路径对象
        """
        path = self._to_absolute(self.document_root, relative_path)
        return self._normalize(path, expect_file=path.suffix != "")

    def get_root_path(self, name: str) -> Path:
        """读取 `relative_to_root` 中声明的已解析路径

        Args:
            name (str): 路径别名

        Returns:
            Path: 解析后的绝对路径对象
        """
        return self.root_relative[name]

    def get_document_path(self, name: str) -> Path:
        """读取 `relative_to_document` 中声明的已解析路径

        Args:
            name (str): 路径别名

        Returns:
            Path: 解析后的绝对路径对象
        """
        return self.document_relative[name]


@dataclass(slots=True)
class WebSocketClientConfig:
    """WebSocket 客户端模式平台实例配置

    Attributes:
        adapter: 适配器类型名称，如 "onebot"
        connection_type: 连接类型
        access_token: 访问令牌
        url: WS client 目标地址 (host:port)，必填
        source_name: 来源标识，默认取平台条目 key
        enabled: 是否启用
    """
    adapter: str
    """适配器类型名称"""
    connection_type: Literal["WebSocket_client"] = "WebSocket_client"
    """连接类型"""
    access_token: str | None = None
    """访问令牌"""
    url: str
    """WS client 目标地址 (host:port)"""
    source_name: str = ""
    """来源标识（为空时自动取平台条目 key"""
    enabled: bool = True
    """是否启用"""


@dataclass(slots=True)
class WebSocketServerConfig:
    """WebSocket 服务端模式平台实例配置

    Attributes:
        adapter: 适配器类型名称，如 "onebot"
        connection_type: 连接类型
        access_token: 访问令牌
        host: WS server 监听地址
        port: WS server 监听端口
        source_name: 来源标识，默认取平台条目 key
        enabled: 是否启用
    """
    adapter: str
    """适配器类型名称"""
    connection_type: Literal["WebSocket_server"] = "WebSocket_server"
    """连接类型"""
    access_token: str | None = None
    """访问令牌"""
    host: str = "127.0.0.1"
    """WS server 监听地址"""
    port: int = 8080
    """WS server 监听端口"""
    source_name: str = ""
    """来源标识（为空时自动取平台条目 key"""
    enabled: bool = True
    """是否启用"""


@dataclass(slots=True)
class HttpAdapterConfig:
    """HTTP 模式平台实例配置

    Attributes:
        adapter: 适配器类型名称，如 "onebot"
        connection_type: 连接类型
        access_token: 访问令牌
        url: HTTP 目标地址 (host:port)
        host: HTTP 监听地址
        port: HTTP 监听端口
        source_name: 来源标识，默认取平台条目 key
        enabled: 是否启用
    """
    adapter: str
    """适配器类型名称"""
    connection_type: Literal["http"] = "http"
    """连接类型"""
    access_token: str | None = None
    """访问令牌"""
    url: str | None = None
    """HTTP 目标地址 (host:port)"""
    host: str = "127.0.0.1"
    """HTTP 监听地址"""
    port: int = 8080
    """HTTP 监听端口"""
    source_name: str = ""
    """来源标识（为空时自动取平台条目 key"""
    enabled: bool = True
    """是否启用"""


PlatformInstanceConfig = Union[WebSocketClientConfig, WebSocketServerConfig, HttpAdapterConfig]
"""平台实例配置联合类型，由 connection_type 区分具体变体"""


@dataclass(slots=True)
class PlatformsConfig:
    """聚合所有平台配置

    Attributes:
        instances: key=平台名称, value=PlatformInstanceConfig
    """
    instances: dict[str, PlatformInstanceConfig] = field(default_factory=dict)
    """平台实例字典"""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PlatformsConfig":
        """从原始 JSON 字典构建 PlatformsConfig

        Args:
            data: {"平台名": {...字段...}, ...} 或 None

        Returns:
            PlatformsConfig 实例
        """
        if not data:
            return cls()
        instances: dict[str, PlatformInstanceConfig] = {}
        for name, raw in data.items():
            if not isinstance(raw, dict):
                continue

            conn_type: str = raw.get("connection_type", "WebSocket_client")
            # 旧别名 "WebSocket" 归一化为 "WebSocket_client"
            if conn_type == "WebSocket":
                conn_type = "WebSocket_client"

            source_name: str = raw.get("source_name") or name

            if conn_type == "WebSocket_client":
                cfg = WebSocketClientConfig(
                    adapter=raw.get("adapter", ""),
                    access_token=raw.get("access_token"),
                    url=raw.get("url") or "127.0.0.1:8080",
                    source_name=source_name,
                    enabled=raw.get("enabled", True),
                )
            elif conn_type == "WebSocket_server":
                cfg = WebSocketServerConfig(
                    adapter=raw.get("adapter", ""),
                    access_token=raw.get("access_token"),
                    host=raw.get("host", "127.0.0.1"),
                    port=raw.get("port", 8080),
                    source_name=source_name,
                    enabled=raw.get("enabled", True),
                )
            else:  # "http"
                cfg = HttpAdapterConfig(
                    adapter=raw.get("adapter", ""),
                    access_token=raw.get("access_token"),
                    url=raw.get("url"),
                    host=raw.get("host", "127.0.0.1"),
                    port=raw.get("port", 8080),
                    source_name=source_name,
                    enabled=raw.get("enabled", True),
                )
            instances[name] = cfg
        return cls(instances=instances)


class atriConfig:
    """提供项目配置参数

    该类初始化并持有项目的全局配置，包括路径配置和通用字典配置
    路径部分为类型化对象,在config.file_path.以下返回为Path对象
    """
    file_path:FilePathConfig
    """路径配置"""
    platforms:PlatformsConfig
    """平台配置"""

    @staticmethod
    def _find_project_root(start_path: Path) -> Path:
        """自动定位项目根目录：以 `main.py` 所在目录作为根目录

        Args:
            start_path (Path): 开始寻找的路径

        Returns:
            Path: 解析后的项目根目录绝对路径

        Raises:
            FileNotFoundError: 如果在任何父目录中都未找到 main.py
        """
        for candidate in [start_path, *start_path.parents]:
            if (candidate / "main.py").exists():
                return candidate.resolve()
        raise FileNotFoundError("无法定位项目根目录：未找到 main.py")

    def __init__(self, config_path: str = "assets/config.json"):
        """初始化 atriConfig

        Args:
            config_path (str): 配置文件相对于项目根目录或绝对路径默认为 "assets/config.json"
        """
        config_path = os.environ.get("ATRI_CONFIG_PATH", config_path)
        project_root = self._find_project_root(Path(__file__).resolve())
        config_file = Path(config_path)
        if not config_file.is_absolute():
            config_file = (project_root / config_file).resolve()

        with open(config_file, "r", encoding="utf-8") as file_handler:
            config_data: Dict[str, Any] = json.load(file_handler)

        self._raw_config: Dict[str, Any] = config_data
        self._config = ConfigObject(config_data)
        self._config_file: Path = config_file

        file_path_data = config_data.get("file_path", {})
        self.file_path = FilePathConfig.from_dict(file_path_data, project_root)

        #平台配置
        platforms_raw: dict[str, Any] = config_data.get("platforms", {})
        platforms_config: PlatformsConfig = PlatformsConfig.from_dict(platforms_raw)
        self._config["platforms"] = platforms_config

    @property
    def config_file_path(self) -> Path:
        """返回当前加载的配置文件绝对路径"""
        return self._config_file

    def __getattr__(self, name: str) -> Any:
        """代理获取配置项

        Args:
            name (str): 配置项名称

        Returns:
            Any: 配置项的值

        Raises:
            AttributeError: 如果配置项不存在
        """
        if name == "file_path":
            return self.file_path
        if hasattr(self._config, name):
            return getattr(self._config, name)
        raise AttributeError(f"配置项 '{name}' 不存在")

    @property
    def all_config(self) -> ConfigObject:
        """获取完整的 ConfigObject 对象

        Returns:
            ConfigObject: 包含所有配置的原始 ConfigObject
        """
        return self._config


if __name__ == "__main__":
    config = atriConfig()
    print(config.file_path.project_root)
    print(config.file_path.document_root)
    print(config.file_path.commands)
    print(config.file_path.chat_manager)
    print(config.file_path.supplier_config_path)
    print(config.file_path.emoji)
    print(config.file_path.root_relative)
    print(config.file_path.document_relative)
