import asyncio
import importlib.util
import json
import os
from logging import Logger
from pathlib import Path
from typing import Any, Dict, List

from mcp.types import CallToolResult

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import ServiceBase, container
from atribot.LLMchat.MCP.mcp_tool_manager import ToolManager
from atribot.LLMchat.MCP.tool_model import FunctionTool, LocalTool, MCPTool
from atribot.LLMchat.MCP.tool_model import ToolSet as ToolSetModel


class ToolRegistry:
    """工具注册表"""

    _registry: list[tuple[dict, Any]] = []

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self.func_list: List[FunctionTool] = []

    def add_func(
        self,
        name: str,
        func_args: Dict,
        desc: str,
        handler,
    ) -> None:
        """添加本地函数调用工具

        Args:
            name: 函数名
            func_args: 参数 properties 字典
            desc: 函数描述
            handler: 异步处理函数
        """
        self.remove_func(name)

        params: dict[str, Any] = {
            "type": "object",
            "properties": func_args,
        }
        _func = LocalTool(
            name=name,
            parameters=params,
            description=desc,
            handler=handler,
        )
        self.func_list.append(_func)
        self.logger.info(f"添加本地函数调用工具: {name}")

    def remove_func(self, name: str) -> None:
        """按名称删除工具"""
        for i, f in enumerate(self.func_list):
            if f.name == name:
                self.func_list.pop(i)
                break

    def get_func(self, name: str) -> FunctionTool | None:
        """按名称获取工具对象"""
        for f in self.func_list:
            if f.name == name:
                return f
        return None

    def empty(self) -> bool:
        """返回工具列表是否为空"""
        return len(self.func_list) == 0

    def sync_mcp_tools(
        self, tools: List[FunctionTool], server_name: str | None = None
    ) -> None:
        """同步 MCP 工具

        Args:
            tools: 新的 MCP 工具列表
            server_name: 指定服务名；为 None 时替换全部 MCP 工具
        """
        if server_name is not None:
            self.func_list = [
                f
                for f in self.func_list
                if not (isinstance(f, MCPTool) and f.mcp_server_name == server_name)
            ]
        else:
            self.func_list = [f for f in self.func_list if not isinstance(f, MCPTool)]
        self.func_list.extend(tools)

    def get_files_in_folder(self, folder_path: str) -> None:
        """扫描工具目录，动态加载每个子目录中的 ``__init__.py``

        每个工具子目录应导出：
        - ``tool_json`` (dict): 工具描述
        - ``main`` (async function): 工具处理函数
        """
        default_module_name = "main"

        for name in os.listdir(folder_path):
            dir_path = os.path.join(folder_path, name)
            if not os.path.isdir(dir_path):
                continue

            file_path = os.path.join(dir_path, "__init__.py")
            if not os.path.exists(file_path):
                self.logger.error(f"文件夹{dir_path}中没有__init__.py文件")
                continue

            spec = importlib.util.spec_from_file_location(name, file_path)
            if spec is None:
                self.logger.error(f"导入模块{file_path} 失败！")
                continue

            module = importlib.util.module_from_spec(spec)
            if module is None:
                self.logger.error(f"获取模块{file_path}中的loader 失败！")
                continue

            try:
                spec.loader.exec_module(module)
            except Exception as e:
                self.logger.error(f"加载模块时发生错误：{e}")
                continue

            func = getattr(module, default_module_name, None)
            if func is None:
                self.logger.error(
                    f"获取模块{file_path}中的函数{default_module_name} 失败！"
                )
                continue

            tool_json = getattr(module, "tool_json", None)
            if tool_json is None:
                self.logger.error(f"获取模块{file_path}中的函数tool_json 失败！")
                continue

            self.add_func(
                name=tool_json["name"],
                func_args={}
                if tool_json.get("properties") is None
                else tool_json["properties"],
                desc=tool_json["description"],
                handler=func,
            )

    def _load_registered_tools(self) -> None:
        """加载通过 ``@register`` / ``@register_tool`` 装饰器注册的工具"""
        for tool_json, func in self._registry:
            self.add_func(
                name=tool_json["name"],
                func_args={}
                if tool_json.get("properties") is None
                else tool_json["properties"],
                desc=tool_json["description"],
                handler=func,
            )

    @classmethod
    def register(cls, tool_json: dict):
        """工具注册装饰器（完整 dict 参数）

        用法::

            @ToolRegistry.register({
                "name": "my_tool",
                "description": "工具描述",
                "properties": {
                    "param": {"type": "string", "description": "参数描述"}
                }
            })
            async def my_tool(param: str):
                ...
        """

        def decorator(func: Any) -> Any:
            cls._registry.append((tool_json, func))
            return func

        return decorator

    @classmethod
    def register_tool(
        cls,
        name: str,
        description: str,
        properties: dict | None = None,
    ):
        """工具注册装饰器（便捷版）

        用法::

            @ToolRegistry.register_tool(
                name="my_tool",
                description="工具描述",
                properties={
                    "param": {"type": "string", "description": "参数描述"}
                }
            )
            async def my_tool(param: str):
                ...
        """
        tool_json = {
            "name": name,
            "description": description,
            "properties": properties or {},
        }

        def decorator(func: Any) -> Any:
            cls._registry.append((tool_json, func))
            return func

        return decorator


class ToolPresetManager:
    """工具预设组管理"""

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self.presets: Dict[str, ToolSetModel] = {}
        self._registry: ToolRegistry | None = None
        self._preset_lock = asyncio.Lock()

    def register_preset(self, preset_name: str, toolset: ToolSetModel) -> None:
        """注册一个工具预设组"""
        self.presets[preset_name] = toolset
        self.logger.info(f"注册工具预设 '{preset_name}': {toolset.names()}")

    def remove_preset(self, preset_name: str) -> None:
        """删除一个工具预设组"""
        self.presets.pop(preset_name, None)

    def load_presets_from_config(self, presets_config: Dict[str, List[str]], registry: "ToolRegistry") -> None:
        """从配置字典批量加载预设组

        Args:
            presets_config: {{预设名: [工具名字符串列表]}}
            registry: 工具注册表，用于将工具名解析为 FunctionTool 实例
        """
        self._registry = registry
        for name, tools in presets_config.items():
            if not isinstance(tools, list):
                self.logger.warning(f"工具预设 '{name}' 的内容不是列表，将被跳过")
                continue
            toolset = ToolSetModel()
            for tool_name in tools:
                func_tool = registry.get_func(tool_name)
                if func_tool is not None:
                    toolset.add_tool(func_tool)
                else:
                    self.logger.warning(f"工具 '{tool_name}' 未在注册表中找到，跳过")
            self.register_preset(name, toolset)
        self.logger.info(f"工具预设共加载 {len(self.presets)} 个")

    async def modify_preset_tools(
        self, preset_name: str, op: str, tools: List[str]
    ) -> None:
        """修改工具预设内的工具 (增/删)，并持久化到 config.json

        Args:
            preset_name: 预设组名称（不可新建）
            op: ``"add"`` 添加工具（自动去重），``"remove"`` 移除工具
            tools: 要操作的工具名称列表

        Raises:
            ValueError: 预设名称不存在、操作类型不支持，或配置文件中找不到预设信息
            RuntimeError: ToolPresetManager 未绑定 ToolRegistry
        """
        if self._registry is None:
            raise RuntimeError("ToolPresetManager 未绑定 ToolRegistry，请先调用 load_presets_from_config")

        async with self._preset_lock:
            if preset_name not in self.presets:
                raise ValueError(f"预设 '{preset_name}' 不存在，禁止非法创建预设")

            toolset = self.presets[preset_name]
            if op == "add":
                for t in tools:
                    func_tool = self._registry.get_func(t)
                    if func_tool is not None:
                        toolset.add_tool(func_tool)
                    else:
                        self.logger.warning(f"工具 '{t}' 未在注册表中找到，无法添加")
            elif op == "remove":
                for t in tools:
                    toolset.remove_tool(t)
            else:
                raise ValueError(f"不支持的操作类型: {op}")

            config_path: Path = container.get("config").config_file_path
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "tool_presets" not in data or preset_name not in data["tool_presets"]:
                raise ValueError(f"config.json 中找不到预设 '{preset_name}'")

            data["tool_presets"][preset_name] = toolset.names()

            # 持久化
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            self.logger.info(
                f"预设 '{preset_name}' 成功执行 {op} 操作，当前包含: {toolset.names()}"
            )

    def get_preset(self, preset_name: str) -> ToolSetModel | None:
        """获取预设对应的工具集合

        Args:
            preset_name: 预设名称

        Returns:
            工具集合，若预设不存在则返回 None
        """
        return self.presets.get(preset_name)

    def resolve_toolset(
        self,
        full_toolset: ToolSetModel,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> ToolSetModel:
        """解析工具集合:preset 优先于 names,均未指定时返回全量集合

        Args:
            full_toolset: 全量工具集合（用于按 names 筛选）
            names: 工具名称列表
            preset: 预设名称

        Returns:
            解析后的工具集合
        """
        if preset is not None:
            if toolset := self.presets.get(preset):
                return toolset
            else:
                self.logger.warning(f"工具预设 '{preset}' 不存在，将返回空工具集合")
                return ToolSetModel()
        if names is not None:
            return full_toolset.filter_by_names(names)
        return full_toolset


class ToolSchemaCache:
    """Schema 格式化与缓存"""

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self._openai_cache: tuple[list, list] | None = None
        self._anthropic_cache: list | None = None
        self._google_cache: dict | None = None

    def build_tool_description_cache(self, func_list: List[FunctionTool]) -> None:
        """基于给定的工具列表构建三种 API 格式的 Schema 缓存"""
        self._openai_cache = (
            self._format_openai(func_list, omit_empty_parameter_field=False),
            self._format_openai(func_list, omit_empty_parameter_field=True),
        )
        self._anthropic_cache = self._format_anthropic(func_list)
        self._google_cache = self._format_google(func_list)
        self.logger.info("已缓存所有激活的 MCP 和本地工具描述")

    @staticmethod
    def _format_openai(
        func_list: List[FunctionTool], omit_empty_parameter_field: bool = False
    ) -> list:
        """转换为 OpenAI function calling 格式"""
        _l = []
        for f in func_list:
            if not f.active:
                continue
            func_ = {
                "type": "function",
                "function": {
                    "name": f.name,
                    "description": f.description,
                },
            }
            func_["function"]["parameters"] = f.parameters
            if not f.parameters.get("properties") and omit_empty_parameter_field:
                del func_["function"]["parameters"]
            _l.append(func_)
        return _l

    @staticmethod
    def _format_anthropic(func_list: List[FunctionTool]) -> list:
        """转换为 Anthropic API 格式"""
        tools = []
        for f in func_list:
            if not f.active:
                continue
            tool = {
                "name": f.name,
                "description": f.description,
                "input_schema": {
                    "type": "object",
                    "properties": f.parameters.get("properties", {}),
                    "required": f.parameters.get("required", []),
                },
            }
            tools.append(tool)
        return tools

    @staticmethod
    def _format_google(func_list: List[FunctionTool]) -> dict:
        """转换为 Google GenAI API 格式"""

        supported_types = {
            "string", "number", "integer", "boolean", "array", "object", "null",
        }
        supported_formats = {
            "string": {"enum", "date-time"},
            "integer": {"int32", "int64"},
            "number": {"float", "double"},
        }

        def convert_schema(schema: dict) -> dict:
            if "anyOf" in schema:
                return {"anyOf": [convert_schema(s) for s in schema["anyOf"]]}

            result: dict[str, Any] = {}
            if "type" in schema and schema["type"] in supported_types:
                result["type"] = schema["type"]
                if "format" in schema and schema["format"] in supported_formats.get(
                    result["type"], set()
                ):
                    result["format"] = schema["format"]
            else:
                result["type"] = "null"

            for k in (
                "title", "description", "enum", "minimum", "maximum",
                "maxItems", "minItems", "nullable", "required",
            ):
                if k in schema:
                    result[k] = schema[k]

            if "properties" in schema:
                properties = {}
                for key, value in schema["properties"].items():
                    prop_value = convert_schema(value)
                    if "default" in prop_value:
                        del prop_value["default"]
                    properties[key] = prop_value
                if properties:
                    result["properties"] = properties

            if "items" in schema:
                result["items"] = convert_schema(schema["items"])

            return result

        tools = [
            {
                "name": f.name,
                "description": f.description,
                **({"parameters": convert_schema(f.parameters)}),
            }
            for f in func_list
            if f.active
        ]

        declarations: dict[str, Any] = {}
        if tools:
            declarations["function_declarations"] = tools
        return declarations


    def get_openai(
        self,
        omit_empty_parameter_field: bool = False,
        toolset: ToolSetModel | None = None,
    ) -> list:
        """获取 OpenAI 格式工具描述，可按 ToolSet 过滤"""
        if self._openai_cache is None:
            return []
        cache_list = (
            self._openai_cache[1] if omit_empty_parameter_field else self._openai_cache[0]
        )
        if toolset is None:
            return cache_list
        names_set = {t.name for t in toolset}
        return [t for t in cache_list if t["function"]["name"] in names_set]

    def get_anthropic(self, toolset: ToolSetModel | None = None) -> list:
        """获取 Anthropic 格式工具描述，可按 ToolSet 过滤"""
        if self._anthropic_cache is None:
            return []
        if toolset is None:
            return self._anthropic_cache
        names_set = {t.name for t in toolset}
        return [t for t in self._anthropic_cache if t["name"] in names_set]

    def get_google(self, toolset: ToolSetModel | None = None) -> dict:
        """获取 Google GenAI 格式工具描述，可按 ToolSet 过滤"""
        if self._google_cache is None:
            return {}
        if toolset is None:
            return self._google_cache

        names_set = {t.name for t in toolset}
        declarations: dict[str, Any] = {}
        if "function_declarations" in self._google_cache:
            filtered = [
                t
                for t in self._google_cache["function_declarations"]
                if t["name"] in names_set
            ]
            if filtered:
                declarations["function_declarations"] = filtered
        return declarations


class ToolCalls(ServiceBase):
    """工具调用"""

    @classmethod
    def factory(cls, config: atriConfig) -> ToolCalls:
        instance = cls(config.file_path.tool_calls)
        instance._preset_manager.load_presets_from_config(config.tool_presets, instance._registry)
        return instance

    def __init__(self, tool_path: Path) -> None:
        self.logger: Logger = container.get("log")
        self._tool_manager: ToolManager = container.get("MCP")

        # 子组件
        self._registry = ToolRegistry(self.logger)
        self._preset_manager = ToolPresetManager(self.logger)
        self._schema_cache = ToolSchemaCache(self.logger)

        # 加载本地工具
        self._registry.get_files_in_folder(str(tool_path))
        self._registry._load_registered_tools()

        # 同步 MCP 工具（可能尚未发现，后续通过回调增量更新）
        mcp_tools = self._tool_manager.get_mcp_func_tools()
        if mcp_tools:
            self._registry.sync_mcp_tools(mcp_tools, server_name=None)

        # 构建初始缓存
        self._schema_cache.build_tool_description_cache(self._registry.func_list)

        # 注册 MCP 工具变更回调
        self._tool_manager.set_on_tools_changed(self._on_mcp_tools_changed)


    @classmethod
    def register(cls, tool_json: dict):
        """工具注册装饰器"""
        return ToolRegistry.register(tool_json)

    @classmethod
    def register_tool(cls, name: str, description: str, properties: dict | None = None):
        """工具注册装饰器便捷版"""
        return ToolRegistry.register_tool(name, description, properties)


    async def calls(
        self, tool_name: str, arguments_str: str, message_data: Any = None
    ) -> CallToolResult | Any:
        """调用工具

        Args:
            tool_name: 工具名
            arguments_str: JSON 字符串参数
            message_data: 可选的聊天消息上下文

        Returns:
            工具执行结果

        Raises:
            Exception: 工具未找到
        """
        func_tool = self._registry.get_func(tool_name)
        if func_tool is None:
            raise Exception(f"Request function {tool_name} not found.")
        return await self._execute_tool(func_tool, arguments_str, message_data)

    async def _execute_tool(
        self, func_tool: FunctionTool, arguments_str: str, message_data: Any = None
    ) -> Any:
        """统一工具执行分发 —— 委托给 func_tool.execute() 多态方法

        - LocalTool: 调用 handler,自动注入 message_data
        - MCPTool: 通过 MCP 客户端会话调用远程工具
        """
        args: dict = json.loads(arguments_str)
        return await func_tool.execute(message_data=message_data, **args)


    async def _on_mcp_tools_changed(
        self, server_name: str | None, mcp_func_list: List[FunctionTool]
    ) -> None:
        """当 ToolManager 中 MCP 工具发生变更时触发"""
        self._registry.sync_mcp_tools(mcp_func_list, server_name=server_name)
        self._schema_cache.build_tool_description_cache(self._registry.func_list)
        self.logger.info(
            f"MCP 工具已同步 (server={server_name}, total={len(self._registry.func_list)})"
        )

    def _build_full_toolset(self) -> ToolSetModel:
        """从当前注册表构建全量工具集合"""
        toolset = ToolSetModel()
        for func_tool in self._registry.func_list:
            toolset.add_tool(func_tool)
        return toolset

    def get_func_desc_openai_style(
        self,
        omit_empty_parameter_field: bool = False,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> list:
        """获取 OpenAI 格式工具描述，支持按 preset 或 names 过滤"""
        full = self._build_full_toolset()
        resolved = self._preset_manager.resolve_toolset(full, names, preset)
        return self._schema_cache.get_openai(omit_empty_parameter_field, toolset=resolved)

    def get_func_desc_anthropic_style(
        self,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> list:
        """获取 Anthropic 格式工具描述，支持按 preset 或 names 过滤"""
        full = self._build_full_toolset()
        resolved = self._preset_manager.resolve_toolset(full, names, preset)
        return self._schema_cache.get_anthropic(toolset=resolved)

    def get_func_desc_google_genai_style(
        self,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> dict:
        """获取 Google GenAI 格式工具描述，支持按 preset 或 names 过滤"""
        full = self._build_full_toolset()
        resolved = self._preset_manager.resolve_toolset(full, names, preset)
        return self._schema_cache.get_google(toolset=resolved)

    def build_tool_description_cache(self) -> None:
        """重建工具描述缓存"""
        self._schema_cache.build_tool_description_cache(self._registry.func_list)

    def register_preset(self, preset_name: str, toolset: ToolSetModel) -> None:
        """注册一个工具预设组"""
        self._preset_manager.register_preset(preset_name, toolset)

    def remove_preset(self, preset_name: str) -> None:
        """删除一个工具预设组"""
        self._preset_manager.remove_preset(preset_name)

    def load_presets_from_config(self, presets_config: Dict[str, List[str]]) -> None:
        """从配置字典批量加载预设组"""
        self._preset_manager.load_presets_from_config(presets_config, self._registry)

    async def modify_preset_tools(
        self, preset_name: str, op: str, tools: List[str]
    ) -> None:
        """修改工具预设内的工具 (增/删)，并持久化到 config.json"""
        await self._preset_manager.modify_preset_tools(preset_name, op, tools)
        self._schema_cache.build_tool_description_cache(self._registry.func_list)

    @property
    def presets(self) -> Dict[str, ToolSetModel]:
        """工具预设字典"""
        return self._preset_manager.presets

    @property
    def func_list(self) -> List[FunctionTool]:
        """当前所有已加载工具列表"""
        return self._registry.func_list