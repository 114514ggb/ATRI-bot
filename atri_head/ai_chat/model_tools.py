tools = [
    {
        "type": "function",
        "function": {
            "name": "send_speech_message",
            "description": "将文本内容转换为语音消息并进行发送，支持发送中文、英文、日语。适用于需要语音输出的交互场景，建议使用口语化表达并避免代码等特殊符号。",
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
    {
        "type": "function",
        "function": {
            "name": "send_text_message",
            "description": "用来在单次交互中发送文本消息,但是后仍可继续使用其他功能，适用于需要连续操作的多步骤场景。消息内容将直接发送给用户。",
            "parameters": {            
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "需要直接呈现给用户的文本内容",
                    }
                }
            },
            "required": ["message"]
        }
    },
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

from ..Basics.qq_send_message import QQ_send_message
from gradio_client import Client
from .bigModel_api import bigModel_api
from .universal_async_ai_api import universal_ai_api
from .async_open_ai_api import async_openAI
import importlib.util
import os
import json

class tool_calls:
    code_url = "document\code.py"
    """python代码运行路径"""

    def __init__(self):
        self.passing_message = QQ_send_message()
        self.tools_functions_dict = {
        }
        self.tools_functions_dict_qq = {
            'send_speech_message': self.send_speech_message,
            'send_image_message': self.send_image_message,
            'send_text_message': self.send_text_message,
        }
        self.tools = tools
        self.load_additional_tools() # 加载额外工具
        self.model = bigModel_api(tools=self.tools)
        
        # self.deepseek = universal_ai_api(tools=self.tools)
        self.deepseek = async_openAI(
            api_key = "sk-0NLKe1sBs6ZGw2iD68E6161872544aCdA7E01bE088DdF4F4",
            base_url = "https://aihubmix.com/v1",
            tools=self.tools
        )

    async def calls(self, tool_name, arguments_str, qq_TestGroup):
        """调用工具"""
        if tool_name in self.tools_functions_dict|self.tools_functions_dict_qq:

            if arguments_str == "{}":   
                return await self.tools_functions_dict[tool_name]()
            elif tool_name in self.tools_functions_dict_qq: 
                return await self.tools_functions_dict_qq[tool_name](**(json.loads(arguments_str)|{"qq_TestGroup":qq_TestGroup}))
            else:
                return await self.tools_functions_dict[tool_name](**json.loads(arguments_str))
            
        else:
            Exception("Unknown tool")

    def load_additional_tools(self):
        """加载额外工具"""
        print("加载模型tools...")
        tools_functions_dict, tools_json = self.get_files_in_folder()
        self.tools_functions_dict.update(tools_functions_dict)
        self.tools = tools_json + self.tools
        print("加载模型tools完成!\n")


    def get_files_in_folder(self):
        """获取返回文件夹中的所有工具函数和工具json"""

        folder_path = "atri_head\\ai_chat\\tools\\"
        default_module_name = "main"
        tools_functions_dict = {}
        tools_json = []

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
                
                tools_json.append(self.generate_integrity_tools_json(tool_json))

                tools_functions_dict[name] = func

        return tools_functions_dict,tools_json

    def generate_integrity_tools_json(self,tool_json):
        """生成工具完整json"""

        tool_json_integrity = {
            "type": "function",
            "function": {
                "name": tool_json["name"],
                "description": tool_json["description"],
                "parameters": {
                    "type": "object",
                    "properties": tool_json["properties"],
                }
            }
        }

        if tool_json["properties"] is None:
            tool_json_integrity["function"]["parameters"]  = {"type": "object", "properties": {}}
        else:
            tool_json_integrity["function"]["required"] = list(tool_json["properties"].keys())

        return tool_json_integrity
     
    async def send_text_message(self, message, qq_TestGroup):
        """发送文本消息"""
        await self.passing_message.send_group_message(qq_TestGroup,message)

        return {"send_text_message": "文本消息已发送"}
    
    async def send_speech_message(self, message, qq_TestGroup):
        """发送语音消息"""
        url = self.text_to_speech(message)
        await self.passing_message.send_group_audio(qq_TestGroup, url)

        return {"speech_message": "语音消息已发送"}
    
    async def send_image_message(self, prompt, qq_TestGroup):
        """生成发送图片消息"""
        url = self.model.generate_image(prompt)['data'][0]['url']
        await self.passing_message.send_group_pictures(qq_TestGroup,url,local_Path_type=False)
        print("图片发送成功")
        return {"image_message": "图片消息已发送"}
    
    def text_to_speech(self, text):
        """文本转语音,返回语音路径"""
        client = Client("http://localhost:9872/")
        result = client.predict(
                        "E:\\ffmpeg\\.......我为了夏生先生行动需要理由吗.mp3",
                        # "E:\\ffmpeg\\啊我真是太高性能了.mp3",	
                        # str (filepath on your computer (or URL) of file) in '请上传3~10秒内参考音频，超过会报错！' Audio component
                        "あ，私です夏生さんのために動く理由が必要なんですか",
                        # "あ、なんて高性能なの、私は！",	
                        # str in '参考音频的文本' Textbox component
                        "日文",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '参考音频的语种' Dropdown component
                        text,	# str in '需要合成的文本' Textbox component
                        "多语种混合",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '需要合成的语种' Dropdown component
                        "凑四句一切",	# str in '怎么切' Radio component
                        30,	# float (numeric value between 1 and 100) in 'top_k' Slider component
                        1,	# float (numeric value between 0 and 1) in 'top_p' Slider component
                        1,	# float (numeric value between 0 and 1) in 'temperature' Slider component
                        False,	# bool in '开启无参考文本模式。不填参考文本亦相当于开启。' Checkbox component
                        fn_index=3
        )
        return result
