from ..Basics.qq_send_message import QQ_send_message
from .model_api.bigModel_api import async_bigModel_api
# from .model_api.async_open_ai_api import async_openAI
from ..Basics import Basics
from .model_api.universal_async_ai_api import universal_ai_api
import asyncio
import importlib.util
import os
import json
# from pprint import pp

class tool_calls:
    """
    工具调用类
    """

    def __init__(self):
        self.passing_message = QQ_send_message()
        self.basics = Basics()
        self.mcp_tool = self.basics.mcp_tool
        """掌管MCP的""" 
        self.tools_functions_dict = {
        }
        self.tools_functions_dict_qq = {
            'send_speech_message': self.send_speech_message,
            'send_image_message': self.send_image_message,
            # 'send_text_message': self.send_text_message,
        }
        self.tools = tools
        
        #tool
        self.mcp_service_queue = asyncio.Queue()
        self.mcp_service_task = asyncio.create_task(self.mcp_tool.mcp_service_selector())#mcp控制方法
        self.mcp_tool.mcp_service_queue.put_nowait({"type": "init"})#初始化所有MCP客户端
        self.load_additional_tools()
        
        #ai_api
        self.model = async_bigModel_api()
        self.chat_request = universal_ai_api(
            self.basics.config.model.connect.api_key,
            self.basics.config.model.connect.base_url
        )
        self.chat_request.model_parameters |= dict(self.basics.config.model.chat_parameter)
        
    
        # self.chat_request = async_openAI(
        #     api_key = "sk-0NLKe1sBs6ZGw2iD68E6161872544aCdA7E01bE088DdF4F4",
        #     base_url = "https://aihubmix.com/v1",
        # )
        


    async def calls(self, tool_name, arguments_str, group_ID):
        """调用工具"""
        if tool_name in self.tools_functions_dict_qq:
            try:
                
                if arguments_str == "{}":   
                    return await self.tools_functions_dict_qq[tool_name]({"group_ID":group_ID})
                else: 
                    return await self.tools_functions_dict_qq[tool_name](**(json.loads(arguments_str)|{"group_ID":group_ID}))
                
            except TypeError as e:
                print(f"函数调用参数错误: {e}")
            except KeyError as e:
                print(f"工具函数未实现: {e}")
        elif func_tool := self.mcp_tool.get_func(tool_name):
            #MCP工具的调用
            return await func_tool.execute(**json.loads(arguments_str))
        else:
            raise Exception(f"Request function {tool_name} not found.")


    def load_additional_tools(self)->list:
        """加载额外工具"""
        print("加载模型tools...")
        
        self.get_files_in_folder()

        self.tools = self.tools + self.mcp_tool.get_func_desc_openai_style()
        print("加载模型tools完成!\n")
        return self.tools


    def get_files_in_folder(self):
        """获添加文件夹中的所有工具函数和工具json"""

        folder_path = "atri_head/ai_chat/tools/"
        default_module_name = "main"

        for name in os.listdir(folder_path):
            dir_path = os.path.join(folder_path, name)
            if os.path.isdir(dir_path):

                file_path = os.path.join(dir_path, "__init__.py")
                if not os.path.exists(file_path):
                    print(f"文件夹{dir_path}中没有__init__.py文件")
                    continue 

                # module_name = f"tools.{name}"

                spec = importlib.util.spec_from_file_location(name, file_path)
                
                if spec is None:
                    print(f"导入模块{file_path} 失败！")
                    continue

                module = importlib.util.module_from_spec(spec)

                if module is None:
                    print(f"获取模块{file_path}中的loader 失败！")
                    continue

                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    print(f"加载模块时发生错误：{e}")
                    continue

                func = getattr(module, default_module_name, None)
                if func is None:
                    print(f"获取模块{file_path}中的函数{default_module_name} 失败！")
                    continue
                
                tool_json = getattr(module, "tool_json", None)
                if tool_json is None:
                    print(f"获取模块{file_path}中的函数tool_json 失败！")
                    continue
                
                self.mcp_tool.add_func(
                    name = tool_json["name"],
                    func_args = {} if tool_json["properties"] is None else tool_json["properties"],
                    desc = tool_json["description"],
                    handler = func
                )

    def get_all_tools_json(self)->list:
        """获取默认的全部工具json"""
        return tools + self.mcp_tool.get_func_desc_openai_style()


    def generate_integrity_tools_json(self, tool_json:dict):
        """生成一个工具的完整json"""
        
        properties:dict = tool_json.get("properties") or {}
        #允许properties没有，或值为None
        
        tool_json_integrity = {
            "type": "function",
            "function": {
                "name": tool_json["name"],
                "description": tool_json["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                }
            }
        }
        
        if properties:
            tool_json_integrity["function"]["required"] = list(properties.keys())
        
        return tool_json_integrity
     
    # async def send_text_message(self, message, group_ID):
    #     """发送文本消息"""
    #     await self.passing_message.send_group_message(group_ID,message)

    #     return {"send_text_message": f"已发送:{message}"}
    
    async def send_speech_message(self, message, group_ID):
        """发送语音消息"""
        url = await self.basics.AI_interaction.speech_synthesis(message)
        await self.passing_message.send_group_audio(group_ID, url)

        return {"send_speech_message": f"已发送语音内容：{message}"}
    
    async def send_image_message(self, prompt, group_ID):
        """生成发送图片消息"""
        url = await self.model.generate_image(prompt)
        await self.passing_message.send_group_pictures(group_ID,url,local_Path_type=False)
        # print("图片发送成功")
        return {"send_image_message": "图片成功发送"}
    

tools = [
    {
        "type": "function",
        "function": {
            "name": "send_speech_message",
            "description": "在需要你发语音或是让你说话的时候使用,将文本内容转换为语音消息并进行发送(使用后不会结束工具调用)，支持发送中文、英文、日语，建议使用口语化表达并避免代码等特殊符号",
            "parameters": {            
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "需转换为语音的文本内容（支持中文/英文/日语）",
                    }
                }
            },
            "required": ["message"]
        }
    },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "send_text_message",
    #         "description": "用来发送文本消息(不会结束工具调用,发完后一般调用工具tool_calls_end)，适用于需要连续发多条消息的多步场景。",
    #         "parameters": {            
    #             "type": "object",
    #             "properties": {
    #                 "message": {
    #                     "type": "string",
    #                     "description": "需要直接呈现给用户的文本内容",
    #                 }
    #             }
    #         },
    #         "required": ["message"]
    #     }
    # },
    {
        "type": "function",
        "function": {
            "name": "send_image_message",
            "description": "这是你的画板,图像生成工具，能够根据文字描述自动生成对应的图片，并将生成的图片发送给用户。适用于需要将文本转化为视觉内容的场景。",
            "parameters": {            
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "需要生成的图片内容",
                    }
                }
            },
            "required": ["prompt"]
        }
    },    
]