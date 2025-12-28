from atribot.core.service_container import container
from atribot.core.types import Context, GroupContext, PrivateContext, LLMGroupChatCondition
# from collections import defaultdict
from typing import Dict,List
from logging import Logger
import datetime




class ChatManager:
    """管理聊天实例类（异步安全）"""
    
    def __init__(
        self,
        default_play_role: str = "none",
        group_messages_max_limit: int = 20,
        private_messages_max_limit: int = 20,
        group_LLM_max_limit: int = 20,
        character_folder: str = "atribot/LLMchat/character_setting"
    ):
        self.logger: Logger = container.get("log")
        self.group_dict: Dict[int, GroupContext] = {}
        """存储群组上下文实例"""
        self.private_dict:Dict[int, PrivateContext] = {}
        """存储私聊上下文实例"""
        self.default_play_role = default_play_role
        """默认扮演角色"""
        self.group_max_record = group_messages_max_limit
        """群消息最大记录数"""
        self.private_max_record = private_messages_max_limit
        """私聊最大记录数"""
        self.LLM_max_record = group_LLM_max_limit
        """LLM聊天的轮数"""
        self.character_folder = character_folder
        """角色设定文件夹路径"""
        self.play_role_list: Dict[str, str] = {"none": ""}
        """角色预设字典"""
        
        self._load_character_settings()
    
    def get_private_context(self, user_id: int) -> PrivateContext:
        """获取指定群的PrivateContext实例
        
        Args:
            user_id: 用户ID
            
        Returns:
            PrivateContext: 私聊上下文实例
        """
        if private_example := self.private_dict.get(user_id):
            return private_example
        else:
            chat_context = Context(
                messages = [],
                user_max_record = self.private_max_record,
                play_role = self.play_role_list.get(
                    self.default_play_role, 
                    self.play_role_list["none"]
                )
            )
            
            private_example = self.private_dict[user_id] = \
            PrivateContext(
                user_id = user_id,
                chat_context = chat_context
            )
            
            return private_example
        
    def get_group_context(self, group_id: int) -> GroupContext:
        """获取指定群的GroupContext实例
        
        Args:
            group_id: 群组ID
            
        Returns:
            GroupContext: 群组上下文实例
        """
        if group_example := self.group_dict.get(group_id):
            return group_example
        else:
            chat_context = Context(
                messages = [],
                user_max_record = self.LLM_max_record,
                play_role = self.play_role_list.get(
                    self.default_play_role, 
                    self.play_role_list["none"]
                )
            )
            
            group_example = self.group_dict[group_id] = \
            GroupContext(
                group_id=group_id,
                play_roles=self.default_play_role,
                chat_context=chat_context,
                group_max_record=self.group_max_record
            )
            
            return group_example
        
        
    async def store_group_chat(self, group_id: str, context: Context) -> None:
        """存储指定群的LLM聊天上下文
        
        Args:
            group_id: 群组ID
            context: 要存储的上下文对象
        """
        group_context = self.get_group_context(group_id)
        async with group_context.async_lock:
                group_context.chat_context = context


    async def store_private_chat(self, user_id: int, context: Context) -> None:
        """存储指定用户的私聊聊天上下文
        
        Args:
            user_id: 用户ID
            context: 要存储的上下文对象
        """
        private_context = self.get_private_context(user_id)
        async with private_context.async_lock:
            private_context.chat_context = context
    
    async def get_group_messages(self, group_id: int) -> List[str]:
        """返回群消息内容"""
        return list(self.get_group_context(group_id).messages)

    def get_group_LLM_decision_parameters(self, group_id:int)->LLMGroupChatCondition:
        """返回LLM聊天决策参数对象"""
        return self.get_group_context(group_id).LLM_chat_decision_parameters
    
    async def get_group_window_msg_count(self, group_id: int)->int:
        """返回一个群的近期消息数量统计

        Args:
            group_id (str): 指定群号

        Returns:
            int: 消息计数
        """
        return (await self.get_group_context(group_id)).time_window.get()
        
    async def add_message_record(
        self,
        data: dict,
        message_text: str,
    ) -> tuple[List[str],GroupContext] | None:
        """添加消息到群组上下文
        
        Args:
            data: 原始响应数据
            message_text: 消息数据
        Returns:
            tuple[List[str],GroupContext]|None: 返回列表和群对象，或是没满足条件返回None
        """
        if message_type := data.get("message_type"): 
        
            if message_type == 'group':
                
                group_context: GroupContext = self.get_group_context(data["group_id"])
                
                if data.get("message_sent_type") == "self":
                    group_context.LLM_chat_decision_parameters.time_window.add()
                # else:
                #     #提取图像url到缓存
                #     group_context.data_extract_img_url(data)
                
                return await group_context.add_group_chat_message(
                        (
                            "<MESSAGE>"
                            f"<qq_id>{data['user_id']}</qq_id>"
                            f"<nick_name>{data['sender']['nickname']}</nick_name>"
                            f"<time>{datetime.datetime.fromtimestamp(data['time']).strftime('%Y-%m-%d %H:%M:%S')}</time>\n"
                            f"<user_message>{message_text[:1000] if len(message_text)>1000 else message_text}</user_message>"
                            "</MESSAGE>"
                        )
                    )
            
            elif message_type == 'private':
                
                # await self._set_private_messages(
                #     data['sender']['user_id'],
                #     message_text
                # )
                
                return None
             

        else:
            #应该基本都是非聊天事件
            return None
        
    
    async def reset_group_chat(self, group_id: int) -> None:
        """重置指定群的LLM聊天上下文
        
        Args:
            group_id: 群组ID
        """
        group_context = self.get_group_context(group_id)
        async with group_context.async_lock:
            group_context.chat_context.clear()
            self.logger.info(f"已重置群{group_id}的聊天上下文")

    
    async def set_group_role(self, group_id: int, role_key: str) -> bool:
        """设置指定群的扮演角色
        
        Args:
            group_id: 群组ID
            role_key: 角色键名
            
        Returns:
            bool: 是否设置成功
        """
        group_context = self.get_group_context(group_id)
        
        async with group_context.async_lock:
            if role_key in self.play_role_list:
                group_context.play_roles = role_key
                group_context.chat_context.play_role = self.play_role_list[role_key]
            else:
                raise ValueError("指定了不存在的角色键名!")
            
        await self.reset_group_chat(group_id)
        self.logger.info(f"已设置群{group_id}的角色为: {role_key}")
        return
    
    async def get_group_role_str(self, group_id: int)->str:
        """获取指定群聊的聊天人设

        Args:
            group_id (int): 群组ID

        Returns:
            str: 人设文本
        """
        return self.get_group_context(group_id).chat_context.play_role
    
    async def clear_group_role(self, group_id: int) -> None:
        """清除指定群的自定义角色，恢复为默认角色
        
        Args:
            group_id: 群组ID
        """
        group_context = self.get_group_context(group_id)
        async with group_context.async_lock:
            
            group_context.play_roles = self.default_play_role
            group_context.chat_context.play_role = self.play_role_list.get(
                self.default_play_role, 
                self.play_role_list["none"]
            )
            await self.reset_group_chat(group_id)
            self.logger.info(f"已清除群{group_id}的自定义角色，恢复为默认角色")
    
    
    def anew_character_settings(self) -> None:
        """重新加载角色设定"""
        self.play_role_list = {"none": ""}
        self._load_character_settings()
        
    
    def _load_character_settings(self) -> None:
        """加载角色设定文件"""
        import os
        
        if not os.path.exists(self.character_folder):
            self.logger.warning(f"角色设定文件夹不存在: {self.character_folder}")
            return
        
        for character_setting in os.listdir(self.character_folder):
            if character_setting.endswith(".txt"):
                key = os.path.splitext(character_setting)[0]
                file_path = os.path.join(self.character_folder, character_setting)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    if len(content) > 20000:
                        content = content[:20000]
                        self.logger.warning(f"角色设定文件 '{character_setting}' 内容超过2万字，已自动截断")
                    
                    self.play_role_list[key] = content
                    self.logger.debug(f"已加载角色设定: {key}")
                    
                except Exception as e:
                    self.logger.error(f"加载角色设定文件 '{character_setting}' 失败: {e}")
    
    