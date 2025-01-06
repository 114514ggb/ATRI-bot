from .ImplementationCommand import *
from .Basics import *
from .textMonitoring import textMonitoring
import time

class group_message_processing():
    """群消息处理类"""
    
    def __init__(self,base_url, token, model):
        self.basics = Basics(base_url, token, model)
        self.command_processor = command_processor()
        self.textMonitoring = textMonitoring()
        self.basics.Command.syncing_locally()#同步数据库
        self.command_processor.Load_additional_commands()#加载额外指令

    async def main(self,data,qq_white_list):
        """主消息处理函数"""
        if 'group_id' in data and data['group_id'] in qq_white_list: # 判断是否在白名单中

            qq_TestGroup = data['group_id']
            message = ""

            if 'message' in data:   # 提取消息内容并确保是字符串
                message_objects = data['message']
                message = ''.join([m['data']['text'] for m in message_objects if m['type'] == 'text'])

            if data['post_type'] == 'message' and data['message_type'] == 'group' and  {'type': 'at', 'data': {'qq': '168238719'}} in data['message']:                
            # 检查是否是群消息事件并且是目标群消息而且是at机器人
                
                print(f"Processed message: {message}")
                await self.receive_event_at(data,qq_TestGroup,message) #at@事件处理
            
            elif self.basics.Command.blacklist_intercept(data["user_id"]): #黑名单检测

                await self.receive_event(data,qq_TestGroup,message) #非at@事件处理

        elif 'self_id' in data:
            print("其他消息")

    async def receive_event_at(self,data,qq_TestGroup,message):
        """at@事件处理"""  

        if "/" in message:#命令处理

            # await self.command_processor.main(message,qq_TestGroup,data)#测试，执行指令时创建一个新进程

            start_time = time.perf_counter()
            await self.command_processor.command_processing(message,qq_TestGroup,data)
            end_time = time.perf_counter()
            print("指令耗时：", end_time - start_time, "秒")

        else:
            try:

                if self.basics.Command.blacklist_intercept(data['user_id']):
                    await self.at_chat(qq_TestGroup,message)#聊天处理
                else:
                    raise Exception("检测到黑名单内人员")
                    

            except Exception as e:
                await self.basics.QQ_send_message.send_group_message(qq_TestGroup,"聊天出错了，请稍后再试!\nType Error:"+str(e))

        return "ok"

    async def receive_event(self,data,qq_TestGroup,message):
        """非at@事件处理"""

        if  data['user_id'] != data['self_id']: #排除自己发送的消息

            await self.textMonitoring.monitoring(message,qq_TestGroup,data)
            
                    
    async def at_chat(self,qq_TestGroup,message):
        """与用户聊天"""
        await self.basics.QQ_send_message.send_group_message(qq_TestGroup,"该功能正在施工中！谢谢您的耐心等待！")
        return "ok"

        message = self.basics.AI_interaction.prompt_model(message)#prompt提示词处理

        self.basics.AI_interaction.Update_message("user",message)

        response_message, response_entirety = self.basics.AI_interaction.chat(self.basics.AI_interaction.messages)#请求模型响应

        argument = f"模型: {response_entirety['model']}\n总耗时:{response_entirety['total_duration']/1000000000}s\n加载模型耗时:{response_entirety['load_duration']/1000000000}s\n提示词评估耗时:{response_entirety['prompt_eval_duration']/1000000000}s"

        self.basics.QQ_send_message.send_group_message(qq_TestGroup,response_message)#发送文字信息

        self.basics.QQ_send_message.send_group_message(qq_TestGroup, argument)#发送模型信息 

        self.basics.QQ_send_message.send_group_audio(qq_TestGroup,self.basics.AI_interaction.speech_synthesis(response_message))#发送语音信息
        
        self.basics.AI_interaction.Update_message("assistant",message)

