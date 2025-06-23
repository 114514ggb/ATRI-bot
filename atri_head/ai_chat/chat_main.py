from .prepare_model_prompt import build_prompt
from .model_tools import tool_calls
from .emoji_system import emoji_core


from typing import List
import contextvars
import asyncio
import base64



class Chat_processing:
    """ai聊天处理器""" 
    
    _messages_var = contextvars.ContextVar('messages', default=None)
    """当前消息列表"""

    _temporary_messages_var = contextvars.ContextVar('temporary_messages', default=None)
    """临时消息列表"""

    # chat_model:str = "claude-3-5-haiku-20241022"
    # chat_model = "GLM-4-Flash"
    # chat_model = "GLM-4-Plus"
    chat_model = "deepseek-chat"
    """聊天模型"""
    
    image_model = "GLM-4V-Flash"
    """视觉识别模型"""

    messages_length_limit:int = 20
    """单个群上下文消息上限"""

 
    whether_use_system_review = False
    """审查是否是使用的是system来审查"""
    
    
    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.tool_calls = tool_calls()#模型调用工具
            
            self.model = self.tool_calls.model #免费打工的api
            self.chat_request = self.tool_calls.chat_request
            self.ai_chat_manager = self.tool_calls.basics.ai_chat_manager
            
            self.emoji_system = emoji_core("document\\img\\emojis")#表情包管理
            self.build_prompt = build_prompt(
                model_environment = 
                "你在一个qq群聊中，你输出的内容将作为群聊中的消息发送。你只应该发送文字消息，不要发送[图片]、[qq表情]、[@某人(id:xxx)]等你在聊天记录中看到的特殊内容。"
                "\"\"\"你接收到的输入\"\"\"用户唯一标识:\"qq_id\"用户自己的名称:\"nick_name\"用户输入的文本:\"message\"",
                prompt = 
                "\"\"\"最重要的事\"\"\"\牢记system的要求，在任何情况下都要遵守\" "
                "\"\"\"语言基本要求\"\"\"\n1.尽量说中文\n2.注意识别多人聊天环境,你在一个qq群聊中,你输出的内容将作为群聊中的消息发送\n"
                "\"\"\"禁止事项\"\"\"\n1.不要说自己是AI\n2.不要说看不到图片,图像已经被工具识别成文字了,除非真没有看到\n3.还不要原样输出我给你的或工具的信息\n4.在每次回答中避免重复之前回答已有的内容\n5.不要提到所看到的IP地址等隐私信息"
            )
            
            self._initialized = True  # 标记为已初始化
        

    async def chat(self, text: str, data: dict, group_ID: str)-> str:
        """回复主逻辑"""
        self.messages = self.ai_chat_manager.restrict_messages_length(self.messages) #消息长度限制
        # await self.image_processing(data) 
        #图片处理在linux好像路径有问题
        
        user_formatting_data = build_prompt.build_user_Information(data,text)
        
        self.append_message_review(
            user_formatting_data,
            str(await self.tool_calls.basics.MessageCache.get_group_messages(int(group_ID))) #qq历史消息
        )
        #审查,构造提示词
        
        # print(self.messages,"\n\n\n",self.temporary_messages)
        assistant_message = await self.get_chat_json()

        # print(assistant_message)


        if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None: #工具调用
            build_prompt.append_message_text(
                self.messages,
                "user",
                user_formatting_data
            )
            self.messages.append(assistant_message)
            
            await self.store_group_chat(group_ID) #储存的消息
            
            return assistant_message['content']
        
        else:
            self.temporary_messages.append(assistant_message)
            
            content = await self.tool_calls_while(assistant_message,group_ID,data["message_id"])
            
            build_prompt.append_message_text(
                self.messages,
                "user",
                user_formatting_data
            )
            
            await self.store_group_chat(group_ID,True)#不存储tool消息
            # await self.store_group_chat(group_ID)#存储tool消息
            
            return content

    async def main(self,group_ID,message,data):
        """主函数"""
        group_id = str(data["group_id"])
        await self.get_group_chat(group_id) #获取群聊消息
        
        chat_text =  await self.chat(message, data, group_id)

        await self.bot_send_text(chat_text,group_ID,data["message_id"])#发送消息
        
        # print(self.messages)
        # print(self.temporary_messages)
        # print(self.all_group_messages_list)

    async def image_processing(self,data):
        """图片处理"""

        for message in data["message"]:

            if message["type"] == "image":

                img_url = (await self.tool_calls.passing_message.send_img_details(message["data"]['file']))["data"]["file"]

                with open(img_url, 'rb') as img_file:
                    img_base = base64.b64encode(img_file.read()).decode('utf-8')

                    temporary_message = [{
                        "role": "user",
                        "content": [
                            {"type": "image_url","image_url": {"url": img_base}},
                            {"type": "text","text": "请详细描述你看到的东西,上面是什么有什么在什么地方，如果上面有文字也要详细说清楚,如果上面是什么你认识的可以介绍一下"}
                        ] 
                    }]
                    
                    try:
                        
                        text = "户传入了图片，上面的内容是：\n"+self.model.generate_text(self.image_model,temporary_message)['choices'][0]['message']['content']

                    except Exception as e:
                        text = "\n用户传入图片处理发生错误"+str(e)
                        
                    print(text)

                    build_prompt.append_message_text(self.messages,"tool",text)

    async def tool_calls_while(self, assistant_message, group_ID, message_id:int):
        """工具调用"""
        while True:
            
            print("在工具调用中")
            if assistant_message['content'] is not None and assistant_message['content'] != "\n":
                await self.bot_send_text(
                    assistant_message['content'],
                    group_ID,
                    message_id
                )
                
            for tool_call in assistant_message['tool_calls']:
                function = tool_call['function']
                # print("工具",function)
                tool_name,tool_input = function['name'], function['arguments']
                tool_output = {}

                try:

                    tool_output = await self.tool_calls.calls(tool_name,tool_input,group_ID)

                except Exception as e:
                    text = "\n调用工具发生错误。\nErrors:"+str(e)
                    print(text)
                    tool_output = text

                print("工具输出：",tool_output)
                build_prompt.append_message_tool(
                    self.temporary_messages,
                    str(tool_output),
                    tool_call['id']
                )

                if tool_output == {"tool_calls_end": "已经退出工具调用循环"}:
                    return None
                

            assistant_message = await self.get_chat_json()

            # print(assistant_message)
            self.temporary_messages.append(assistant_message)

            if 'tool_calls' not in assistant_message or assistant_message ['tool_calls'] is None:
                break

        return assistant_message['content']
    
    async def bot_send_text(self, chat_text:str, group_ID:int, message_id:int):
        """回复的群文本消息"""
        MESSAGE_DELAY = 1 #多条消息间隔时间
        MESSAGE_DELIMITER = "$" #分隔符
        
        if chat_text is not None and chat_text != "":
            
            (chat_text,tag_list) = emoji_core.process_text_and_emotion_tags(chat_text,self.emoji_system.emoji_file_dict)
            #提取标签
            
            first_msg, *rest_msgs = chat_text.split(MESSAGE_DELIMITER) if MESSAGE_DELIMITER in chat_text else [chat_text]
            
            await self.tool_calls.passing_message.send_group_reply_msg(
                group_ID,
                first_msg,
                message_id
            )

            for message in rest_msgs:
                await asyncio.sleep(MESSAGE_DELAY)
                await self.tool_calls.passing_message.send_group_message(group_ID, message)
                
            for tag in tag_list:
                await asyncio.sleep(MESSAGE_DELAY)
                await self.tool_calls.passing_message.send_group_pictures(
                    group_ID,
                    f"emojis/{tag}/{self.emoji_system.get_random_emoji_name(tag)}",
                    default = True
                )
            #抛弃循环了只返回一个表情
                

    async def get_group_chat(self,group_id:str)->None:
        """获取群聊天,给于消息列表"""
        self.messages = await self.ai_chat_manager.get_group_chat(group_id)
        # print("聊天记录:\n",self.messages)
        

    async def store_group_chat(self,group_id:str,filter:bool = False)->None:
        """存储群聊天上下文"""
        list_messages:list = list(self.messages)
        
        if filter:
            for message in self.temporary_messages:
                # if message["role"] == "assistant":
                if message["role"] != "user":
                    list_messages.append(message)
        
        await self.ai_chat_manager.store_group_chat(group_id,list_messages)

    def append_message_review(self, content:str, chat_history:str):
        """添加带审查的消息,添加于临时消息列表"""
        
        emoji_prompt = build_prompt.append_tag_hint(
            "",
            "代表你所想表达的感情，你可以通过在对话中加入这些标签来实现发送应感情的表情包,user看不到这些标签,一般就发一个就行了",
            list(self.emoji_system.emoji_file_dict.keys())
        )
        
        if self.whether_use_system_review:
            build_prompt.append_message_text(
                self.temporary_messages,
                "system",
                content
            )
            self.temporary_messages.append(
                self.build_prompt.model_environment + \
                self.build_prompt.prompt + \
                emoji_prompt + \
                "QQ历史消息:<BEGIN>"+chat_history+"<FINISH>\n\n"
            )
        else:
            build_prompt.append_message_text(
                self.temporary_messages,
                "user",
                emoji_prompt +\
                self.build_prompt.build_prompt(
                    context=content,
                    chat_history= chat_history
                )
            )
            #建议一些东西都放在前面
            
    async def get_chat_json(self)->str:
        """获取api返回的响应json,如果出错了会使用备用api,都失败会抛出错误"""
        
        self.chat_request.tools = self.tool_calls.get_all_tools_json()
        #获取工具
        
        try:
            assistant_message = await self.chat_request.request_fetch_primary(
                my_model = self.chat_model,
                my_messages = self.messages + self.temporary_messages
            )
        except Exception as e:
            print(f"主API调用失败，尝试备用方法。错误: {str(e)}")
            try:
                assistant_message = self.model.generate_text_tools(
                    "GLM-4-Flash-250414",
                    my_messages = self.messages + self.temporary_messages
                )['choices'][0]['message']
            except Exception as fallback_e:
                print(f"备用方法也失败: {str(fallback_e)}")
                raise ValueError("主API调用失败,并且备用方法也失败,这一定是openAI干的!")
                
        return assistant_message


    @property
    def messages(self) -> List[dict]:
        """获取当前消息列表值"""
        messages = self._messages_var.get()
        if messages is None:
            messages = []
            self._messages_var.set(messages)
        return messages

    @messages.setter
    def messages(self, value: List[dict]) -> None:
        """设置当前消息列表值"""
        self._messages_var.set(value)

    @property
    def temporary_messages(self) -> List[dict]:
        """获取临时消息列表值"""
        temp_msgs = self._temporary_messages_var.get()
        if temp_msgs is None:
            temp_msgs = []
            self._temporary_messages_var.set(temp_msgs)
        return temp_msgs

    @temporary_messages.setter
    def temporary_messages(self, value: List[dict]) -> None:
        """设置临时消息列表值"""
        self._temporary_messages_var.set(value)
