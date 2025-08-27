from atribot.core.types import Context
from collections import defaultdict
from typing import List, Dict
import asyncio
import os




class context_management:
    """群上下文和角色设置管理类(异步安全)"""
    async_group_locks = defaultdict(asyncio.Lock)
    """群的异步锁"""
    
    def __init__(
        self,
        default_play_role:str = "none",
        messages_length_limit:int=20,
        folder_path:str = "atribot/LLMchat/character_setting"
    ):
        self.all_group_messages: Dict[str, Context] = {}
        """所有群消息上下文"""
        
        self.group_play_roles: Dict[str, str] = {}
        """各群独立的扮演角色"""
        
        self.default_play_role: str = default_play_role
        """默认全局模型扮演角色名"""
        
        self.play_role_list: Dict[str, str] = {"none": ""}
        """角色预设字典"""
        
        self.messages_length_limit: int = messages_length_limit
        """单个群上下文消息上限"""
        
        self.folder_path:str = folder_path
        """扮演角色文件路径"""
        
        self._load_character_settings()
    
    async def get_group_chat(self, group_id: str) -> Context:
        """获取指定群的聊天上下文
        
        Args:
            group_id: 群组ID
            
        Returns:
            Context: 上下文实例
        """
        async with self.async_group_locks[group_id]:
                if group_id not in self.all_group_messages:
                    role_content = self.play_role_list[self.group_play_roles.get(group_id, self.default_play_role)]
                    self.all_group_messages[group_id] = Context(
                        messages=[],
                        user_max_record=self.messages_length_limit,
                        Play_role=role_content
                    )
                    
                return self.all_group_messages[group_id]
    
    async def store_group_chat(self, group_id: str, context: Context) -> None:
        """存储指定群的聊天上下文
        
        Args:
            group_id: 群组ID
            context: 要存储的上下文对象
        """
        async with self.async_group_locks[group_id]:
                self.all_group_messages[group_id] = context

    async def update_group_chat(self, group_id: str, new_messages: List[dict]) -> None:
        """更新指定群的聊天上下文，向原有添加新消息
        
        Args:
            group_id: 群组ID
            new_messages: 要添加的新消息列表
        """
        async with self.async_group_locks[group_id]:
                if group_id not in self.all_group_messages:
                    role_content = self.play_role_list[self.group_play_roles.get(group_id, self.default_play_role)]
                    context = Context(
                        messages=[],
                        user_max_record=self.messages_length_limit,
                        Play_role=role_content
                    )
                    self.all_group_messages[group_id] = context
                else:
                    context = self.all_group_messages[group_id]
                
                context.extend(new_messages)
        
    async def reset_group_chat(self, group_id: str) -> None:
        """重置指定群的聊天上下文
        
        Args:
            group_id: 群组ID
        """
        async with self.async_group_locks[group_id]:
                self.all_group_messages[group_id].clear()
    
    async def set_group_role(self, group_id: str, role_key: str) -> None:
        """设置指定群的扮演角色
        
        Args:
            group_id: 群组ID
            role_key: 角色键名
        """
        async with self.async_group_locks[group_id]:
                if role_key in self.play_role_list:
                    self.group_play_roles[group_id] = role_key
                    if group_id in self.all_group_messages:
                        self.all_group_messages[group_id].Play_role = self.play_role_list[role_key]
                        self.all_group_messages[group_id].clear()
    
    async def clear_group_role(self, group_id: str) -> None:
        """清除指定群的自定义角色，恢复为默认角色
        
        Args:
            group_id: 群组ID
        """
        async with self.async_group_locks[group_id]:
                if group_id in self.group_play_roles:
                    if group_id in self.all_group_messages:
                        self.all_group_messages[group_id].Play_role = self.play_role_list[self.default_play_role]
                        self.all_group_messages[group_id].clear()
                        
    
    def _load_character_settings(self) -> None:
        """加载角色设定文件"""
        for character_setting in os.listdir(self.folder_path):
            if character_setting.endswith(".txt"):
                key = os.path.splitext(character_setting)[0]
                with open(os.path.join(self.folder_path, character_setting), "r", encoding="utf-8") as f:
                    self.play_role_list[key] = f.read()
        
        
        
if __name__ == "__main__":
    async def my_main():
        ACM = context_management("ATRI")
        print(ACM.play_role_list["ATRI"])
        await ACM.store_group_chat(123456,["aaaaaa","bbbbb"])
        print(await ACM.get_group_chat(123456))
        await ACM.store_group_chat(123456,[])
        print(await ACM.reset_group_chat(123456))
        await ACM.set_group_role(123456,"文言文版")
        await ACM.reset_group_chat(123456)
        print(await ACM.get_group_chat(123456))
    
    asyncio.run(my_main())
