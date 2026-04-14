import asyncio
from abc import ABC, abstractmethod
from logging import Logger

from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_db_basics import AsyncDatabaseBase
from atribot.core.event_trigger.event_trigger import EventTrigger
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import AtSegment, ChatMessage
from atribot.core.type.chat_types import GroupContext
from atribot.LLMchat.chat import GroupChat, PrivateChat
from atribot.LLMchat.initiative_chat import initiativeChat
from atribot.LLMchat.memory.memory_system import memorySystem


class message_router():
    """分流消息主类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.db:AsyncDatabaseBase = container.get("database")
        self.send_message:QQAPIClient = container.get("SendMessage")
        self.group_manage = group_manage()
        self.private_manage = private_manage()
        self.group_set = {None}
    
    async def main(self, data:dict):
        """主消息处理逻辑"""
        
        if data.get('post_type') in ["message","message_sent"]:
            chat_message = ChatMessage.from_chat_event(data)
        else:
            if data.get("meta_event_type") ==  'heartbeat':
                return #目前心跳的话就跳过吧
            else:
                self.logger.debug(f"原始消息:\n{data}")
            chat_message = ChatMessage.from_not_chat_event(data)
        
        if chat_message.group_id:  #有群号就是群相关的直接简单分发处理了
            await self.group_manage.handle_message(chat_message, chat_message.group_id)
        else:
            #私聊相关处理
            await self.private_manage.handle_message(chat_message)

        if chat_message.segments:
            asyncio.create_task(self.store_data(chat_message)) #存储消息
        

    async def store_data(self, chat_message:ChatMessage)->None:
        """存储消息"""
        data = chat_message.primeval
        group_id = chat_message.group_id
        
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
            users = {"user_id":chat_message.user_id,"nickname":data['sender']['nickname']}
            message ={"message_id":chat_message.message_id,"content":chat_message.user_cq_message,"timestamp":data["time"],"group_id":group_id,"user_id":chat_message.user_id}
        except Exception as e:
            self.logger.warning(f"获取db存储参数失败:{e}")
            return
        
        try:
            async with self.db as db:
                await db.add_user(**users)
                await db.add_message(**message)
                
            return
            
        except Exception as e:
            self.logger.warning(f"数据存储失败:{e}")
            return

    
    
class message_manage(ABC):
    """消息处理基类"""
    def __init__(self):
        self.permissions_management:PermissionsManagement = container.get("PermissionsManagement")
        self.command_system:CommandSystem = container.get("CommandSystem")
        self.send_message:QQAPIClient = container.get("SendMessage")
        self.memory_system:memorySystem = container.get("memorySystem")
        self.chat_manager:ChatManager = container.get("ChatManager")
        self.logger:Logger = container.get("log")
        self.initiative_chat = initiativeChat()
    
    @abstractmethod
    async def handle_message(self, message: ChatMessage) -> None:
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
        config = container.get("config")
        self.group_white_list:list = config.group_white_list
        self.root_user_id:int = config.root_user_id
        self.group_chet:GroupChat = container.get("GroupChat")
        self.event_trigger:EventTrigger = container.get("EventTrigger")
        
    async def handle_message(self, chat_message:ChatMessage, group_id: int) -> None:
        data = chat_message.primeval
        user_id = chat_message.user_id
        
        if group_id not in self.group_white_list and not (user_id == self.root_user_id):
            return
        
        group_context: GroupContext = await self.chat_manager.get_group_context(group_id)
        group_context.time_window.add()

        chat_message.update_llm_formatted_message()

        if data.get("message_sent_type") == "self":
            self.logger.debug(f"收到自己的群消息:{data}")
            asyncio.create_task(self._process_memory_summary(chat_message, group_id))
            return

        self.logger.debug(f"Received group message: {data}")

        has_permission = self.permissions_management.check_access(user_id)

        if self._check_is_mentioned(chat_message):
            #@处理
            await self._handle_mentioned_message(has_permission, chat_message, group_context)
        elif has_permission:
            try:
                if not await self.initiative_chat.decision(chat_message, group_context):
                    await self.event_trigger.dispatch(chat_message,data)
            except Exception as e:
                self.error_occurred(e, "事件触发器")
        
        asyncio.create_task(self._process_memory_summary(chat_message, group_id))

    def _check_is_mentioned(self, chat_message:ChatMessage) -> bool:
        """检查bot是否被 @"""
        for segment in chat_message.segments:
            if isinstance(segment,AtSegment) and segment.user_id == str(chat_message.self_id):
                return True
        return False
    
    async def _handle_mentioned_message(self,has_permission, chat_message:ChatMessage, group_context):
        """处理被 @ 的消息逻辑"""
        # 指令处理
        if chat_message.pure_text.startswith("/"):
            try:
                await self.command_system.dispatch_command(chat_message)
            except Exception as e:
                self.error_occurred(e, "命令处理模块")
                await self.send_message.send_group_mgs(
                    chat_message.group_id, 
                    f"ATRI用手挠了挠脑袋,这个指令执行出现了问题😕\nType Error:\n{e}"
                )
            return 

        #聊天处理
        if has_permission:
            try:
                # await self.group_chet.step(message)
                await self.initiative_chat.decision(chat_message, group_context, at=True)
            except Exception as e:
                self.error_occurred(e, "群聊聊天模块")
                await self.send_message.send_group_mgs(
                    chat_message.group_id, 
                    f"ATRI的聊天模块抛出了个错误,疑似不够高性能!\nType Error:\n{e}"
                )
        else:
            self.logger.info(f"黑名单人员被拒绝聊天{chat_message.user_id}!") 


    async def _process_memory_summary(self, chat_message:ChatMessage, group_id):
        """处理记忆存储与总结"""
        try:
            if summary_needed := await self.chat_manager.add_message_record(chat_message):
                messages, group_context = summary_needed
                async with group_context.summarizing() as ctx:
                    if ctx is not None:
                        self.logger.info(f"开始总结 {group_id} 群消息!")
                        await self.memory_system.extract_stored_group_message(
                            messages_str=messages,
                            bot_id=chat_message.self_id,
                            group_id=group_id
                        )
        except Exception as e:
            self.error_occurred(e, "记忆总结模块")
                        

class private_manage(message_manage):
    """私聊消息处理类"""

    def __init__(self):
        super().__init__()
        self.private_chat: PrivateChat = container.get("PrivateChat")

    async def handle_message(self, chat_message: ChatMessage) -> None:
        data = chat_message.primeval
        user_id = chat_message.user_id

        if data.get("message_sent_type") == "self":
            return

        return
    
        self.logger.debug(f"Received private message: {data}")
        chat_message.update_llm_formatted_simplify_message()

        has_permission = self.permissions_management.check_access(user_id)

        # if chat_message.pure_text.startswith("/"):
        #     if has_permission:
        #         try:
        #             await self.command_system.dispatch_command(chat_message)
        #         except Exception as e:
        #             self.error_occurred(e, "私聊命令处理模块")
        #             await self.send_message.send_private_msg(
        #                 user_id=user_id,
        #                 message=f"ATRI用手挢了挢脑袋,这个指令执行出现了问题😕\nType Error:\n{e}"
        #             )
        #     return

        if has_permission:
            try:
                await self.private_chat.step(
                    chat_message,
                    "你正在和用户进行一对一私聊，请认真回复对方的消息"
                )
            except Exception as e:
                self.error_occurred(e, "私聊聊天模块")
                await self.send_message.send_private_msg(
                    user_id=user_id,
                    message=f"ATRI的聊天模块抛出了个错误!Type Error:\n{e}"
                )
        else:
            self.logger.info(f"黑名单人员被拒绝私聊{user_id}!")

