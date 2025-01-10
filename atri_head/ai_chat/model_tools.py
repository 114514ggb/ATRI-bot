tools = [
    {
        "type": "function",
        "function": {
            "name": "get_python_code_result",
            "description": "当你想知道python代码运行结果时非常有用。但是不要使用这个工具来运行恶意代码,或者运行需要大量计算资源的代码,否则可能会被禁止使用这个工具。",
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
            "name": "send_message",
            "description": "当你需要分多次发送消息时非常有用，让你消息不会太长，你也更像一个真人一样。",
            "parameters": {            
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "需要发送的消息",
                    }
                }
            },
            "required": ["message"]
        }
    },    
]

import subprocess
from datetime import datetime
from ..Basics.qq_send_message import QQ_send_message
import json

class tool_calls:
    code_url = "document\code.py"

    def __init__(self):
        self.passing_message = QQ_send_message
        self.tool_functions = {
            'get_python_code_result': self.get_python_code_result,
            'get_current_time': self.get_current_time,
            'send_message': self.send_message,
        }

    async def calls(self, tool_name, arguments_str, qq_TestGroup):
        """调用工具"""
        if tool_name in self.tool_functions:
            
            if arguments_str == "{}":   
                return self.tool_functions[tool_name]()
            elif tool_name == "send_message":
                return await self.send_message(json.loads(arguments_str)["message"], qq_TestGroup)
            else:
                return self.tool_functions[tool_name](**json.loads(arguments_str))
        else:
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
    
    async def send_message(self, message, qq_TestGroup):
        """发送消息"""
        await self.passing_message.send_group_message(qq_TestGroup, message)

        return {"message": "消息已发送"}
