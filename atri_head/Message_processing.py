from .ImplementationCommand.command_processor import command_processor
from .triggerAction.textMonitoring import textMonitoring
from .Basics import Basics


class group_message_processing():
    """群消息处理类"""
    qq_white_list = [] #qq白名单
    first_connect_database = False #是否第一次连接数据库

    def __init__(self, playRole, http_base_url = None, token= None, connection_type = "http",qq_white_list = []):
        self.qq_white_list = qq_white_list
        self.basics = Basics(http_base_url, token, playRole, connection_type)
        self.command_processor = command_processor()
        self.textMonitoring = textMonitoring()
        self.basics.Command.syncing_locally()#同步管理员名单

    async def main(self,data:dict)-> bool:
        """主消息处理函数"""
        
        # print(data)
        
        if 'group_id' in data and data['group_id'] in self.qq_white_list or ('user_id' in data and data['user_id'] == 2631018780): # 判断是否在白名单中

            print("Received event:", data)
            group_ID = data['group_id']
            message = ""

            if 'message' in data:   # 提取消息内容并确保是字符串
                message_objects = data['message']
                message = ''.join([m['data']['text'] for m in message_objects if m['type'] == 'text'])

            if data['post_type'] == 'message' and data['message_type'] == 'group' and  {'type': 'at', 'data': {'qq': '168238719'}} in data['message']:                
            # 检查是否是群消息事件并且是目标群消息而且是at机器人
                
                print(f"Processed message: {message}")
                await self.receive_event_at(data,group_ID,message) #at@事件处理
            
            elif self.basics.Command.blacklist_intercept(data["user_id"]): #黑名单检测

                await self.receive_event(data,group_ID,message) #非at@事件处理
        
        return await self.data_store(data) #数据存储
            

    async def receive_event_at(self,data:dict,group_ID:int,message:str)-> bool:
        """at@事件处理"""  

        if message.startswith(("/", " /")):#命令处理
            # await self.command_processor.main(message,group_ID,data)#测试，执行指令时创建一个新进程

            # start_time = time.perf_counter()
            await self.command_processor.main(message,group_ID,data)
            # end_time = time.perf_counter()
            # print("指令耗时：", end_time - start_time, "秒")
            return True

        else:
            try:

                if self.basics.Command.blacklist_intercept(data['user_id']):
                    
                    await self.basics.AI_interaction.chat.main(group_ID, message, data) #聊天处理
                    return True
                
                else:
                    raise Exception("检测到黑名单内人员")
                    

            except Exception as e:
                await self.basics.QQ_send_message.send_group_message(group_ID,"聊天出错了，请稍后再试!\nType Error:"+str(e))
                return False

        

    async def receive_event(self, data:dict, group_ID:int, message:str):
        """非at@事件处理"""

        if  data['user_id'] != data['self_id']: #排除自己发送的消息

            await self.textMonitoring.monitoring(message,group_ID,data)
            
            return True
        
        return False
        
    async def receive_event_private(self,data):
        """私聊消息处理"""
        pass
    
    async def data_store(self, data:dict) -> bool:
        """数据存储"""
        if not self.first_connect_database:
            
            await self.basics.link_async_database("127.0.0.1","root","180710")
            await self.exit_save() #退出时处理
            
            self.first_connect_database = True
            
            
        if "post_type" in data and data["post_type"] == "message":
            
            text = self.basics.Command.data_processing_text(data=data)
            
            group_name = (await self.basics.QQ_send_message.get_group_info(data["group_id"]))["data"]["group_name"]
            
            try:
                users = {"user_id":data["user_id"],"nickname":data['sender']['nickname']}
                message ={"message_id":data["message_id"],"content":text,"timestamp":data["time"],"group_id":data["group_id"],"user_id":data["user_id"]}
                user_group = {"group_id":data["group_id"],"group_name":group_name}
            except Exception as e:
                print("获取参数失败:",e)
                return None
            
            try:
                async with self.basics.async_database as db:
                    await db.add_user(**users)
                    await db.add_group(**user_group)
                    await db.add_message(**message)
                    
                print("数据存储信息成功!")
                return True
                
            except Exception as e:
                print("数据存储失败:",e)
                await self.basics.async_database.error_close()
                return None

    async def exit_save(self):
        """退出时保存数据"""
        pass
        # db_quit= self.basics.async_database.close_pool #清理数据库
        
        # self.basics.exiter_save.register_async(db_quit)
        
            
            
                        

            
                    

