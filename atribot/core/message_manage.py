from atribot.core.command.async_permissions_management import permissions_management
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.event_trigger.event_trigger import EventTrigger
from atribot.core.command.command_parsing import command_system
from atribot.core.db.atri_async_Database import AtriDB_Async
from atribot.core.service_container import container
from atribot.core.data_manage import data_manage
from atribot.LLMchat.chat import group_chat
from atribot.core.types import rich_data
from abc import ABC, abstractmethod
from logging import Logger


class message_router():
    """分流消息主类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.db:AtriDB_Async = container.get("database")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.group_manage = group_manage()
    
    async def main(self, data:dict):
        """主消息处理逻辑"""
        
        if data.get('post_type') == "message":
            _rich_data = data_manage.rich_data_processing_rich_data(data)
        else:
            if data.get("meta_event_type") !=  'heartbeat':
                self.logger.debug(f"原始消息:\n{data}")
            _rich_data = rich_data(data,"","")
        
        if group_id := data.get("group_id"):            
            await self.group_manage.handle_message(_rich_data, group_id)
        else:
            pass
        
        await self.store_data(_rich_data)
            

    async def store_data(self, rich_data:rich_data)->None:
        """存储消息"""
        data = rich_data.primeval
    
        if "post_type" in data and data["post_type"] == "message":
                
                group_name = (await self.send_message.get_group_info(data["group_id"]))["data"]["group_name"]
                
                try:
                    users = {"user_id":data["user_id"],"nickname":data['sender']['nickname']}
                    message ={"message_id":data["message_id"],"content":rich_data.text,"timestamp":data["time"],"group_id":data["group_id"],"user_id":data["user_id"]}
                    user_group = {"group_id":data["group_id"],"group_name":group_name}
                except Exception as e:
                    self.logger.warning(f"获取db存储参数失败:{e}")
                    return
                
                try:
                    async with self.db as db:
                        await db.add_user(**users)
                        await db.add_group(**user_group)
                        await db.add_message(**message)
                        
                    return
                    
                except Exception as e:
                    self.logger.warning(f"数据存储失败:{e}")
                    await self.db.error_close()
                    return
    
    
    
class message_manage(ABC):
    """消息基类"""
    def __init__(self):
        self.permissions_management:permissions_management = container.get("PermissionsManagement")
        self.command_system:command_system = container.get("CommandSystem")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.logger:Logger = container.get("log")
    
    @abstractmethod
    async def handle_message(self, message: rich_data) -> None:
        """处理接收到的消息"""
        pass

class group_manage(message_manage):
    """群聊消息处理类"""
    
    def __init__(self):
        super().__init__()
        self.group_white_list:list = container.get("config").group_white_list
        self.group_chet:group_chat = container.get("GroupChat")
        self.event_trigger = EventTrigger()
        
    async def handle_message(self, message: rich_data, group_id:int) -> None:
        data = message.primeval
        
        if group_id in self.group_white_list or ('user_id' in data and data['user_id'] == 2631018780):
            
            pure_text = message.pure_text
            self.logger.debug(f"Received group message:{data}")
            
            if data.get('message_type','') == 'group' and  {'type': 'at', 'data': {'qq': str(data["self_id"])}} in data['message']:
                #@处理
                
                if pure_text.startswith("/"):
                    try:
                        await self.command_system.dispatch_command(pure_text,data)
                    except Exception as e:
                        self.logger.error(f"指令处理出现了错误:{e}")
                        await self.send_message.send_group_message(group_id,f"ATRI用手挠了挠脑袋,这个指令执行出现了问题😕\nType Error:\n{e}")
                else:
                    try:
                        if self.permissions_management.check_access(data["user_id"]):
                            
                            await self.group_chet.step(data)

                        else:
                            PermissionError("你好像在黑名单里？")
                    except Exception as e:
                        self.logger.error(f"聊天出现了错误:{e}")
                        await self.send_message.send_group_message(group_id,f"ATRI的聊天模块抛出了个错误,疑似不够高性能!\nType Error:\n{e}")
                        
            elif data['user_id'] != data['self_id']:
                try:
                    
                    await self.event_trigger.dispatch(data,group_id)
                    
                except Exception as e:
                    self.logger.error(f"群非@事件出现了错误:{e}")
        
        

class private_manage(message_manage):
    """私聊消息处理类"""
    
    def __init__(self):
        super().__init__()
