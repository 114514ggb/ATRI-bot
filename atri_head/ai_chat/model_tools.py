tools = [
    {
        "type": "function",
        "function": {
            "name": "get_python_code_result",
            "description": "当你想知道python代码运行结果时非常有用。但是不要使用这个工具来运行恶意代码,或者运行需要大量计算资源的代码,如果有数学问题请用这个工具来计算一下",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "需要运行的python代码,记得print输出结果",
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "当你想知道现在的时间时非常有用。",
            "parameters": {            
                "type": "None",
                "properties": "None"
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_speech_message",
            "description": "可以将文本内容转换为语音并发送出去，让你可以发出声音。",
            "parameters": {            
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "需要发送消息的文本内容",
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
            "description": "这是你的画板,当你想画画时非常有用,可以按照你的描述生成一张图片，然后发送出去。",
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

import subprocess
from datetime import datetime
from ..Basics.qq_send_message import QQ_send_message
from gradio_client import Client
from .bigModel_api import bigModel_api
import json

class tool_calls:
    code_url = "document\code.py"

    def __init__(self):
        self.passing_message = QQ_send_message()
        self.model = bigModel_api(tools=tools)
        self.tool_functions = {
            'get_python_code_result': self.get_python_code_result,
            'get_current_time': self.get_current_time,
        }
        self.tool_functions_async = {
            'send_speech_message': self.send_speech_message,
            'send_image_message': self.send_image_message,
        }

    async def calls(self, tool_name, arguments_str, qq_TestGroup):
        """调用工具"""
        if tool_name in self.tool_functions|self.tool_functions_async:

            if arguments_str == "{}":   
                return self.tool_functions[tool_name]()
            elif tool_name in self.tool_functions_async: 
                return await self.tool_functions_async[tool_name](**(json.loads(arguments_str)|{"qq_TestGroup":qq_TestGroup})) #异步调用
            else:
                return self.tool_functions[tool_name](**json.loads(arguments_str))
            
        else:
            print("Unknown tool")
            Exception("Unknown tool")
                
    def get_python_code_result(self,code:str):
        """获取python代码运行结果"""
        with open(self.code_url, "w", encoding='utf-8') as f:
            f.write(code)

        result = subprocess.run(["python", self.code_url], capture_output=True, text=True)

        if result.returncode != 0:
            return {"error": result.stderr}
        else:
            return {"command_line_interface":result.stdout}
    
    def get_current_time(self):
        """获取当前时间"""

        current_datetime = datetime.now()

        formatted_time = current_datetime.strftime('%Y-%m-%d %H:%M:%S')

        return {"北京_time":formatted_time}
    
    async def send_speech_message(self, message, qq_TestGroup):
        """发送语音消息"""
        url = self.text_to_speech(message)
        await self.passing_message.send_group_audio(qq_TestGroup, url)

        return {"message": "语音消息已发送"}
    
    async def send_image_message(self, prompt, qq_TestGroup):
        """生成发送图片消息"""
        url = self.model.generate_image(prompt)['data'][0]['url']
        await self.passing_message.send_group_pictures(qq_TestGroup,url,local_Path_type=False)
        print("图片发送成功")
        return {"message": "图片消息已发送"}
    
    def text_to_speech(self, text):
        """文本转语音,返回语音路径"""
        client = Client("http://localhost:9872/")
        result = client.predict(
                        "E:\\ffmpeg\.......我为了夏生先生行动需要理由吗.mp3",	# str (filepath on your computer (or URL) of file) in '请上传3~10秒内参考音频，超过会报错！' Audio component
                        "あ，私です夏生さんのために動く理由が必要なんですか",	# str in '参考音频的文本' Textbox component
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
