from .ImplementationCommand import *
from .textMonitoring import textMonitoring
from .Basics import Basics
import time

class group_message_processing():
    """群消息处理类"""
    qq_white_list = [] #qq白名单

    def __init__(self, playRole, http_base_url = None, token= None, connection_type = "http",qq_white_list = []):
        self.qq_white_list = qq_white_list
        self.basics = Basics(http_base_url, token, playRole, connection_type)
        self.command_processor = command_processor()
        self.textMonitoring = textMonitoring()
        self.basics.Command.syncing_locally()#同步数据库
        self.command_processor.Load_additional_commands()#加载额外指令

    async def main(self,data):
        """主消息处理函数"""
        if 'group_id' in data and data['group_id'] in self.qq_white_list: # 判断是否在白名单中

            print("Received event:", data)
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
            pass
            # print("其他消息")

    async def receive_event_at(self,data,qq_TestGroup,message):
        """at@事件处理"""  

        if message[0:2] == " /":#命令处理
            # await self.command_processor.main(message,qq_TestGroup,data)#测试，执行指令时创建一个新进程

            # start_time = time.perf_counter()
            await self.command_processor.command_processing(message,qq_TestGroup,data)
            # end_time = time.perf_counter()
            # print("指令耗时：", end_time - start_time, "秒")

        else:
            try:

                if self.basics.Command.blacklist_intercept(data['user_id']):
                    await self.basics.AI_interaction.chat.main(qq_TestGroup, message, data) #聊天处理
                else:
                    raise Exception("检测到黑名单内人员")
                    

            except Exception as e:
                await self.basics.QQ_send_message.send_group_message(qq_TestGroup,"聊天出错了，请稍后再试!\nType Error:"+str(e))

        return "ok"

    async def receive_event(self,data,qq_TestGroup,message):
        """非at@事件处理"""

        if  data['user_id'] != data['self_id']: #排除自己发送的消息

            await self.textMonitoring.monitoring(message,qq_TestGroup,data)

            
                    

