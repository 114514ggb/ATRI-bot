from atribot.core.command.async_permissions_management import permissions_management
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.event_trigger.event_trigger import EventTrigger
from atribot.core.command.command_parsing import command_system
from atribot.core.db.async_db_basics import AsyncDatabaseBase
from atribot.LLMchat.memory.memiry_system import memorySystem
from atribot.core.service_container import container
from atribot.core.data_manage import data_manage
from atribot.LLMchat.initiative_chat import initiativeChat
from atribot.LLMchat.chat import group_chat
from atribot.core.bot_types import RichData
from abc import ABC, abstractmethod
from logging import Logger




class message_router():
    """分流消息主类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.db:AsyncDatabaseBase = container.get("database")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.group_manage = group_manage()
        self.group_set = set()
    
    async def main(self, data:dict):
        """主消息处理逻辑"""
        
        group_id = data.get("group_id")
        
        if data.get('post_type') in ["message","message_sent"]:
            _rich_data = data_manage.rich_data_processing_rich_data(data)
        else:
            if data.get("meta_event_type") !=  'heartbeat':
                self.logger.debug(f"原始消息:\n{data}")
            _rich_data = RichData(data)
        
        if group_id:            
            await self.group_manage.handle_message(_rich_data, group_id)
        else:
            #私聊处理
            return

        if _rich_data.text:
            await self.store_data(_rich_data,group_id) #存储群消息
            

    async def store_data(self, rich_data:RichData, group_id:int)->None:
        """存储消息"""
        data = rich_data.primeval
        
        if group_id not in self.group_set:
            group_name = (await self.send_message.get_group_info(group_id))["data"]["group_name"]
            self.group_set.add(group_id)
            try:
                user_group = {"group_id": group_id, "group_name": group_name}
                async with self.db as db:
                    await db.add_group(**user_group)
            except Exception as e:
                self.logger.warning(f"群信息存储失败:{e}")
        
        try:
            users = {"user_id":rich_data.user_id,"nickname":data['sender']['nickname']}
            message ={"message_id":data["message_id"],"content":rich_data.text,"timestamp":data["time"],"group_id":group_id,"user_id":rich_data.user_id}
        except Exception as e:
            self.logger.warning(f"获取db存储参数失败:{e}")
            return
        
        try:
            async with self.db as db:
                db:AsyncDatabaseBase
                await db.add_user(**users)
                await db.add_message(**message)
                
            return
            
        except Exception as e:
            self.logger.warning(f"数据存储失败:{e}")
            return

    
    
class message_manage(ABC):
    """消息处理基类"""
    def __init__(self):
        self.permissions_management:permissions_management = container.get("PermissionsManagement")
        self.command_system:command_system = container.get("CommandSystem")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.memiry_system:memorySystem = container.get("memirySystem")
        self.chat_manager:ChatManager = container.get("ChatManager")
        self.logger:Logger = container.get("log")
        self.initiative_chat = initiativeChat()
    
    @abstractmethod
    async def handle_message(self, message: RichData) -> None:
        """处理接收到的消息"""
        pass
    
    def error_occurred(self, error: Exception, text:str) -> None:
        """处理消息处理过程中出现的错误"""
        import traceback
        self.logger.critical(
            f"{text}出现了错误:{error}\n"
            "异常类型: %s\n"
            "详细回溯:\n%s",
            type(error).__name__,  
            ''.join(traceback.format_exception(type(error), error, error.__traceback__)) 
        )

class group_manage(message_manage):
    """群聊消息处理类"""
    
    def __init__(self):
        super().__init__()
        self.group_white_list:list = container.get("config").group_white_list
        self.self_qq = str(container.get("config").account.id)
        self.group_chet:group_chat = container.get("GroupChat")
        self.event_trigger = EventTrigger()
        
    async def handle_message(self, message: RichData, group_id: int) -> None:
        data = message.primeval
        user_id = message.user_id
        
        if group_id not in self.group_white_list and not (user_id == 2631018780):
            return
        
        group_context = self.chat_manager.get_group_context(group_id)
        group_context.time_window.add()

        if data.get("message_sent_type") == "self":
            await self._process_memory_summary(data, message.text, group_id)
            return

        self.logger.debug(f"Received group message: {data}")

        has_permission = self.permissions_management.check_access(user_id)

        if self._check_is_mentioned(data):
            #@处理
            await self._handle_mentioned_message(message.pure_text, data, group_id, has_permission, message, group_context)
        elif has_permission:
            try:
                if not await self.initiative_chat.decision(message, group_context):
                    await self.event_trigger.dispatch(data, group_id)
            except Exception as e:
                self.error_occurred(e, "事件触发器")
        
        await self._process_memory_summary(data, message.text, group_id)

    def _check_is_mentioned(self, data: dict) -> bool:
        """辅助函数：检查是否被 @"""
        for msg in data.get("message", []):
            if msg.get("type") == "at" and str(msg.get("data", {}).get("qq")) == self.self_qq:
                return True
        return False
    
    async def _handle_mentioned_message(self, pure_text:str, data, group_id, has_permission, message, group_context):
        """处理被 @ 的消息逻辑"""
        # 指令处理
        if pure_text.startswith("/"):
            try:
                await self.command_system.dispatch_command(pure_text, data)
            except Exception as e:
                self.error_occurred(e, "命令处理模块")
                await self.send_message.send_group_message(
                    group_id, 
                    f"ATRI用手挠了挠脑袋,这个指令执行出现了问题😕\nType Error:\n{e}"
                )
            return 

        #聊天处理
        if has_permission:
            try:
                # await self.group_chet.step(message)
                await self.initiative_chat.decision(message, group_context, at=True)
            except Exception as e:
                self.error_occurred(e, "群聊聊天模块")
                await self.send_message.send_group_message(
                    group_id, 
                    f"ATRI的聊天模块抛出了个错误,疑似不够高性能!\nType Error:\n{e}"
                )
        else:
            self.logger.info(f"黑名单人员被拒绝聊天{data["user_id"]}!") 


    async def _process_memory_summary(self, data, text, group_id):
        """处理记忆存储与总结"""
        try:
            if summary_needed := await self.chat_manager.add_message_record(data, text):
                messages, group_context = summary_needed
                async with group_context.summarizing() as ctx:
                    if ctx is not None:
                        self.logger.info(f"开始总结 {group_id} 群消息!")
                        await self.memiry_system.extract_stored_group_message(
                            messages=messages,
                            bot_id=data['self_id'],
                            group_id=group_id
                        )
        except Exception as e:
            self.error_occurred(e, "记忆总结模块")
                        
        

class private_manage(message_manage):
    """私聊消息处理类"""
    
    def __init__(self):
        super().__init__()

