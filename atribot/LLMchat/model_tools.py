from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.core.service_container import container
from logging import Logger
import importlib.util
import os
import json



class tool_calls:
    """
    工具调用类
    """

    def __init__(self):
        self.logger:Logger = container.get("log")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.mcp_tool:FuncCall = container.get("MCP")
        """掌管MCP的""" 
        
        #tool
        self.get_files_in_folder()
        

    async def calls(self, tool_name:str, arguments_str:str):
        """调用工具"""
        if func_tool := self.mcp_tool.get_func(tool_name):
            #MCP工具的调用
            return await func_tool.execute(**json.loads(arguments_str))
        else:
            raise Exception(f"Request function {tool_name} not found.")

    def get_files_in_folder(self):
        """获添加文件夹中的所有工具函数和工具json"""

        folder_path = "atribot/LLMchat/tools"
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