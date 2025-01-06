from .example_plugin import example_plugin
from ...ai_chat.open_ai import OpenAI_api
import subprocess,json
from datetime import datetime

class qwen_code(example_plugin):
    register_order = ["/code", "/代码"]

    model="qwen-plus"
    api_key="sk-bde63eefc4c9480aace5243c3455e038"
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    code_url = "document\code.py"

    role = {
        "role": "system",
        "content": "你叫ATRI,你的中文名是亚托利,一般自称是ATRI,是一个可爱的猫娘机器人,擅长使用Python编程语言,并且精通各种计算机科学知识。用来解决用户的一些问题。你拥有一个python解释器，可以运行python代码，运行后工具会发送给你运行结果，记住不要运行恶意代码,或者运行需要大量计算资源的代码。在有需要时，你尽量多用工具确定你的答案。例子：我问你，1+1等于几？你回答：使用工具计算1+1的结果。",
    }

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
                            "description": "需要运行的python代码",
                        }
                    }
                },
                "required": [
                    "code"
                ]
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "当你想知道现在的时间时非常有用。",
                "parameters": {}
            }
        },    
    ]

    messages = [
        {
            "role": "system",
            "content": "你叫ATRI,你的中文名是亚托利,一般自称是ATRI,是一个可爱的猫娘机器人,擅长使用Python编程语言,并且精通各种计算机科学知识。用来解决用户的一些问题。你拥有一个python解释器，可以运行python代码，运行后工具会发送给你运行结果，记住不要运行恶意代码,或者运行需要大量计算资源的代码。在有需要时，你尽量多用工具确定你的答案。例子：我问你，1+1等于几？你回答：使用工具计算1+1的结果。",
        }
    ]
    """聊天记录"""

    def __init__(self):
        super().__init__()
        self.OpenAI_api = OpenAI_api(self.api_key, self.base_url, self.tools)

    def append_message(self,role,content):
        """添加消息"""
        self.messages.append({"role": role,"content": content})
        return True

    def Request_answer(self):
        """请求回答"""
        return self.OpenAI_api.generate_text_tools(self.model, self.messages)
    
    def get_python_code_result(self,code):
        """获取python代码运行结果"""
        with open(self.code_url, "w", encoding='utf-8') as f:
            f.write(code)

        result = subprocess.run(["python", self.code_url], capture_output=True, text=True)

        if result.returncode != 0:
            return "Errors:"+result.stderr  
        else:
            return result.stdout 
    
    def get_current_time(self):

        current_datetime = datetime.now()

        formatted_time = current_datetime.strftime('%Y-%m-%d %H:%M:%S')

        return f"当前时间：{formatted_time}。"

    
    async def main(self,qq_TestGroup,user_input,data):
        """可调用python的ai"""
        self.store(user_input,qq_TestGroup,data)
        self.basics.Command.verifyParameter(
            self.argument,
            parameter_quantity_max_1=1, parameter_quantity_min_1=0, 
            parameter_quantity_max_2=100, parameter_quantity_min_2=1,
        )

        self.append_message("user",' '.join(self.argument[1]))
        back_message = self.Request_answer()
        print(back_message)

        assistant_output = back_message['choices'][0]['message']

        if  assistant_output['content'] is None:
            assistant_output['content'] = ""
        self.messages.append(assistant_output)

        if assistant_output['tool_calls'] == None: 
            await self.basics.QQ_send_message.send_group_message(qq_TestGroup, assistant_output['content'])
            return
        
        while assistant_output['tool_calls'] != None: #如果有工具调用进入调用循环
            if assistant_output['tool_calls'][0]['function']['name'] == 'get_python_code_result': #如果调用的是python代码

                tool_info = {"name": "get_python_code_result", "role":"tool"}
                code = json.loads(assistant_output['tool_calls'][0]['function']['arguments'])['code']
                tool_info['content'] = self.get_python_code_result(code)
                print(tool_info['content'])
            
            elif assistant_output['tool_calls'][0]['function']['name'] == 'get_current_time': #如果调用的是获取当前时间
                tool_info = {"name": "get_current_time", "role":"tool"}
                tool_info['content'] = self.get_current_time()
                print(tool_info['content'])
                
            self.messages.append(tool_info)
            assistant_output = self.Request_answer()['choices'][0]['message']
            if  assistant_output['content'] is None:
                assistant_output['content'] = ""
            self.messages.append(assistant_output)

        await self.basics.QQ_send_message.send_group_message(qq_TestGroup, assistant_output['content'])

        if len(self.messages) >= 20: #删除消息记录,防止过长
            self.messages = self.messages[-20:]
            self.messages[0] = self.role #人物设定

    async def qwen_code(self,qq_TestGroup,user_input,data):

        await self.main(qq_TestGroup,user_input,data)

        return True