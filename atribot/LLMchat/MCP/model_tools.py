import importlib.util
import json
import os
from logging import Logger
from pathlib import Path
from typing import Any, Dict, List

from mcp.types import CallToolResult

from atribot.core.service_container import container
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall


class tool_calls:
    """
    用于工具调用
    """
    _registry: list[tuple[dict, Any]] = []

    def __init__(self, tool_path:Path):
        self.logger:Logger = container.get("log")
        self.mcp_tool:FuncCall = container.get("MCP")
        
        self.presets: Dict[str, List[str]] = {}
        """工具预设列表"""
        self._openai_cache: tuple[list, list] | None = None
        self._anthropic_cache: list | None = None
        self._google_cache: dict | None = None
        
        #tool
        self.get_files_in_folder(str(tool_path))
        self._load_registered_tools()

    def build_tool_description_cache(self):
        """构建工具描述缓存，在使用工具描述前必须确保调用过该方法。可以通过定时或事件触发"""
        self._openai_cache = (
            self.mcp_tool.get_func_desc_openai_style(omit_empty_parameter_field=False),
            self.mcp_tool.get_func_desc_openai_style(omit_empty_parameter_field=True)
        )
        self._anthropic_cache = self.mcp_tool.get_func_desc_anthropic_style()
        self._google_cache = self.mcp_tool.get_func_desc_google_genai_style()
        self.logger.info("已缓存所有激活的 MCP 和本地工具描述")

    def register_preset(self, preset_name: str, tool_names: List[str]) -> None:
        """注册一个工具预设组"""
        self.presets[preset_name] = list(tool_names)
        self.logger.info(f"注册工具预设 '{preset_name}': {tool_names}")

    def remove_preset(self, preset_name: str) -> None:
        """删除一个工具预设组"""
        self.presets.pop(preset_name, None)

    def load_presets_from_config(self, presets_config: Dict[str, List[str]]) -> None:
        """从配置字典批量加载预设组"""
        for name, tools in presets_config.items():
            if not isinstance(tools, list):
                self.logger.warning(f"工具预设 '{name}' 的内容不是列表，将被跳过")
                continue
            self.register_preset(name, tools)
        self.logger.info(f"工具预设共加载 {len(self.presets)} 个")

    def _resolve_names(
        self,
        names: List[str] | None,
        preset: str | None,
    ) -> List[str] | None:
        """解析工具名称列表:preset 优先于 names"""
        if preset is not None:
            if resolved := self.presets.get(preset):
                return resolved
            else:
                self.logger.warning(f"工具预设 '{preset}' 不存在，将返回空工具列表")
                return []
        return names

    def get_func_desc_openai_style(
        self,
        omit_empty_parameter_field: bool = False,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> list:
        """
        获取 OpenAI 风格的工具描述字典列表

        Args:
            omit_empty_parameter_field (bool, optional): 为 True 时，若工具无参数则省略 parameters 字段。Defaults to False.
            names (List[str] | None, optional): 要筛选的工具名称列表；为 None 时返回所有已激活工具。Defaults to None.
            preset (str | None, optional): 预设组名称，优先于 names,预设不存在时返回空列表。Defaults to None.

        Returns:
            list: OpenAI API 风格的工具描述列表
        """
        if self._openai_cache is None:
            self.build_tool_description_cache()
        names = self._resolve_names(names, preset)
        cache_list = self._openai_cache[1] if omit_empty_parameter_field else self._openai_cache[0]
        
        if names is None:
            return cache_list
        return [tool for tool in cache_list if tool["function"]["name"] in names]

    def get_func_desc_anthropic_style(
        self,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> list:
        """
        获取 Anthropic API 风格的工具描述列表

        Args:
            names (List[str] | None, optional): 要筛选的工具名称列表；为 None 时返回所有已激活工具。Defaults to None.
            preset (str | None, optional): 预设组名称，优先于 names,预设不存在时返回空列表。Defaults to None.

        Returns:
            list: Anthropic API 风格的工具描述列表
        """
        if self._anthropic_cache is None:
            self.build_tool_description_cache()
        names = self._resolve_names(names, preset)
        
        if names is None:
            return self._anthropic_cache
        return [tool for tool in self._anthropic_cache if tool["name"] in names]

    def get_func_desc_google_genai_style(
        self,
        names: List[str] | None = None,
        preset: str | None = None,
    ) -> dict:
        """
        获取 Google GenAI API 风格的工具描述

        Args:
            names (List[str] | None, optional): 要筛选的工具名称列表；为 None 时返回所有已激活工具。Defaults to None.
            preset (str | None, optional): 预设组名称，优先于 names,预设不存在时返回空字典。Defaults to None.

        Returns:
            dict: Google GenAI API 风格的工具描述字典
        """
        if self._google_cache is None:
            self.build_tool_description_cache()
        names = self._resolve_names(names, preset)
        
        if names is None:
            return self._google_cache
            
        declarations = {}
        if self._google_cache and "function_declarations" in self._google_cache:
            filtered_tools = [
                tool for tool in self._google_cache["function_declarations"] 
                if tool["name"] in names
            ]
            if filtered_tools:
                declarations["function_declarations"] = filtered_tools
        return declarations

    @classmethod
    def register(cls, tool_json: dict):
        """工具注册装饰器,如果有message_data参数会自动注入聊天的时候传入的消息

        用法::

            @tool_calls.register({
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
        如果有 message_data 参数会自动注入聊天时传入的消息。

        用法::

            @tool_calls.register_tool(
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

    def _load_registered_tools(self) -> None:
        """加载通过 @tool_calls.register 装饰器注册的工具"""
        for tool_json, func in self._registry:
            self.mcp_tool.add_func(
                name=tool_json["name"],
                func_args={} if tool_json.get("properties") is None else tool_json["properties"],
                desc=tool_json["description"],
                handler=func,
            )

    async def calls(self, tool_name: str, arguments_str: str, message_data: Any = None) -> CallToolResult | Any:
        """调用工具"""
        if func_tool := self.mcp_tool.get_func(tool_name):
            return await func_tool.execute(_message_data=message_data, **json.loads(arguments_str))
        else:
            raise Exception(f"Request function {tool_name} not found.")

    def get_files_in_folder(self, folder_path:str):
        """获添加文件夹中的所有工具函数和工具json"""
        
        default_module_name = "main"

        for name in os.listdir(folder_path):
            dir_path = os.path.join(folder_path, name)
            if os.path.isdir(dir_path):

                file_path = os.path.join(dir_path, "__init__.py")
                if not os.path.exists(file_path):
                    self.logger.error(f"文件夹{dir_path}中没有__init__.py文件")
                    continue 

                # module_name = f"tools.{name}"

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
                    self.logger.error(f"获取模块{file_path}中的函数{default_module_name} 失败！")
                    continue
                
                tool_json = getattr(module, "tool_json", None)
                if tool_json is None:
                    self.logger.error(f"获取模块{file_path}中的函数tool_json 失败！")
                    continue
                
                self.mcp_tool.add_func(
                    name = tool_json["name"],
                    func_args = {} if tool_json["properties"] is None else tool_json["properties"],
                    desc = tool_json["description"],
                    handler = func
                )