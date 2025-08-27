from .ImplementationCommand.command_processor import command_processor
from .triggerAction.textMonitoring import textMonitoring
from .Basics import Basics,Command
from .ai_chat.chat_main import Chat_processing


class group_message_processing():
    """群消息处理类"""
    single_use = False #一次性

    def __init__(self,qq_white_list = []):
        self.qq_white_list = qq_white_list
        """qq白名单"""
        self.basics = Basics()#这个一定要第一个
        self.command_processor = command_processor()
        self.chat_ai = Chat_processing()
        self.textMonitoring = textMonitoring()
        self.Command = Command()
        
        self.Command.syncing_locally()#同步管理员名单

    async def main(self,data:dict)-> bool:
        """主消息处理函数"""
        
        if not self.single_use:
            """一次性处理"""
            
            await self.basics.link_async_database()#连接数据库
            await self.exit_save() #退出时处理
            
            self.single_use = True
        
        # print(data)
        
        if data.get("group_id",0) in self.qq_white_list or ('user_id' in data and data['user_id'] == 2631018780):
            """过滤出群事件"""
            print("Received event:", data)
            group_ID = data['group_id']
            message = ""

            if 'message' in data:   # 提取消息内容并确保是字符串
                message_objects = data['message']
                message = ''.join([m['data']['text'] for m in message_objects if m['type'] == 'text'])

            if self.Command.blacklist_intercept(data["user_id"]):#黑名单检测

                if  data.get('message_type','') == 'group' and  {'type': 'at', 'data': {'qq': str(data["self_id"])}} in data['message']:                
                
                    print(f"at message: {message}")
                    await self.receive_event_at(data,group_ID,message) #at@事件处理
                    
                else:
                    
                    await self.receive_event(data,group_ID,message) #非at@事件处理
            
        await self.data_store(data) #数据存储
        
        return True
            

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
                    
                await self.chat_ai.main(
                    group_ID, 
                    data
                ) 
                return True

            except Exception as e:
                await self.basics.QQ_send_message.send_group_message(group_ID,"聊天出错了，请稍后再试!\nType Error:"+str(e)+"\n请务必联系管理员:2631018780！")
                return False

        
    async def receive_event(self, data:dict, group_ID:int, message:str):
        """非at@事件处理"""
        # rouse_word = ["ATRI","atri"]

        if  data['user_id'] != data['self_id']: #排除自己发送的消息

            # if any(word in message for word in rouse_word):
            #     try:
            #         print(f"尝试回复:{message}")
                    
            #         await self.chat_ai.main(
            #             group_ID, 
            #             data
            #         ) 
            #         return True

            #     except Exception as e:
            #         await self.basics.QQ_send_message.send_group_message(group_ID,"聊天出错了，请稍后再试!\nType Error:"+str(e)+"\n请务必联系管理员:2631018780！")
            #         return False
                
            await self.textMonitoring.monitoring(message,group_ID,data)
            #监控
            
            return True
        
        return False
        
    async def receive_event_private(self,data):
        """私聊消息处理"""
        pass
    
    async def data_store(self, data:dict) -> bool:
        """数据存储"""
        
        data_text = ""
        if data.get('message',False):
            try:
                data_text = self.Command.data_processing_text(data)
                #message字符串化
            except Exception as e: 
                print("\nmessage字符串化失败:",e,"\n原消息:",data)

        await self.basics.MessageCache.cache_system(data=data,message_test=data_text)
        #消息缓存
            
        if "post_type" in data and data["post_type"] == "message":
            
            group_name = (await self.basics.QQ_send_message.get_group_info(data["group_id"]))["data"]["group_name"]
            
            try:
                users = {"user_id":data["user_id"],"nickname":data['sender']['nickname']}
                message ={"message_id":data["message_id"],"content":data_text,"timestamp":data["time"],"group_id":data["group_id"],"user_id":data["user_id"]}
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
        register_async_all = []
        register_async_all.append(self.basics.async_database.close_pool) #清理数据库
        register_async_all.append(self.basics.QQ_send_message.websocketClient.close) #关闭主连接
        register_async_all.append(self.chat_ai.tool_calls.mcp_tool.terminate) #清理MCP客户端
        
        for async_all in register_async_all:
            self.basics.exiter_save.register_async(async_all)

        
            
            
                        

            
                    

