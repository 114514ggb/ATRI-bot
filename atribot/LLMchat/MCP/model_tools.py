import importlib.util
import json
import os
from logging import Logger
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

from atribot.core.service_container import container
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall


class tool_calls:
    """
    工具调用类
    """
    _registry: list[tuple[dict, Any]] = []

    @classmethod
    def register(cls, tool_json: dict):
        """工具注册装饰器

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

    def __init__(self, tool_path:Path):
        self.logger:Logger = container.get("log")
        self.mcp_tool:FuncCall = container.get("MCP")
        """掌管MCP的""" 
        
        #tool
        self.get_files_in_folder(str(tool_path))
        self._load_registered_tools()
        

    def _load_registered_tools(self) -> None:
        """加载通过 @tool_calls.register 装饰器注册的工具"""
        for tool_json, func in self._registry:
            self.mcp_tool.add_func(
                name=tool_json["name"],
                func_args={} if tool_json.get("properties") is None else tool_json["properties"],
                desc=tool_json["description"],
                handler=func,
            )

    async def calls(self, tool_name:str, arguments_str:str)-> CallToolResult | Any:
        """调用工具"""
        if func_tool := self.mcp_tool.get_func(tool_name):
            #MCP工具的调用
            return await func_tool.execute(**json.loads(arguments_str))
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