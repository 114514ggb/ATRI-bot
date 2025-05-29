from collections import defaultdict
from typing import List, Dict
from threading import Lock
import threading
import asyncio
import os

class ai_chat_manager:
    """上下文和角色设置管理类"""
    _lock = threading.Lock()
    _lock_async = asyncio.Lock()
    all_group_locks = defaultdict(Lock)
    folder_path = "atri_head\\ai_chat\\character_setting"
    """默认角色路径"""
    
    def __init__(self,default_play_role:str = "none"):
        self.all_group_messages: Dict[str, List[dict]] = {}
        """所有群消息列表"""
        
        self.group_play_roles: Dict[str, str] = {}
        """各群独立的扮演角色"""
        
        self.default_play_role: str = default_play_role
        """默认全局模型扮演角色名"""
        
        self.play_role_list: Dict[str, str] = {"none": ""}
        """角色预设字典"""
        
        self.messages_length_limit: int = 20
        """单个群上下文消息上限"""
        
        self._load_character_settings()
    
    async def get_group_chat(self, group_id: str) -> List[dict]:
        """获取指定群的聊天记录"""
        async with self._lock_async:
            with self.all_group_locks[group_id]:
                if group_id not in self.all_group_messages:
                    role = self.play_role_list[self.group_play_roles.get(group_id, self.default_play_role)]
                    self.all_group_messages[group_id] = self._create_initial_messages(role)
                return self.all_group_messages[group_id].copy()
    
    async def store_group_chat(self, group_id: str, messages: List[dict]) -> None:
        """存储指定群的聊天记录"""
        async with self._lock_async:
            with self.all_group_locks[group_id]:
                self.all_group_messages[group_id] = messages.copy()
    
    async def reset_group_chat(self, group_id: str) -> None:
        """重置指定群的聊天记录"""
        async with self._lock_async:
            with self.all_group_locks[group_id]:
                role = self.play_role_list[self.group_play_roles.get(group_id, self.default_play_role)]
                self.all_group_messages[group_id] = self._create_initial_messages(role)
    
    
    async def set_group_role(self, group_id: str, role_key: str) -> bool:
        """设置指定群的扮演角色"""
        async with self._lock_async:
            with self.all_group_locks[group_id]:
                if role_key in self.play_role_list:
                    self.group_play_roles[group_id] = role_key
                    return True
                return False
    
    async def clear_group_role(self, group_id: str) -> None:
        """清除指定群的自定义角色，恢复为默认角色"""
        async with self._lock_async:
            with self.all_group_locks[group_id]:
                if group_id in self.group_play_roles:
                    del self.group_play_roles[group_id]
    
    def restrict_messages_length(self, messages: List[dict]) -> List[dict]:
        """限制消息长度"""
        user_message_count = sum(1 for msg in messages if msg['role'] == 'user')
        
        if user_message_count >= self.messages_length_limit:

            trimmed_messages = messages[-15:]
            # 重新添加角色设定
            role = self._get_role_for_messages(trimmed_messages)
            return self._create_initial_messages(role) + trimmed_messages
        return messages
    
    def _create_initial_messages(self, role: str) -> List[dict]:
        """创建带有角色设定的初始消息列表"""
        if not role:
            return []
        return [{"role": "system", "content": role}]
    
    def _get_role_for_messages(self, messages: List[dict]) -> str:
        """从消息列表中提取角色设定"""
        if messages and messages[0]['role'] == 'system':
            return messages[0]['content']
        return ""
    
    def _load_character_settings(self) -> None:
        """加载角色设定文件"""
        for character_setting in os.listdir(self.folder_path):
            if character_setting.endswith(".txt"):
                key = os.path.splitext(character_setting)[0]
                with open(os.path.join(self.folder_path, character_setting), "r", encoding="utf-8") as f:
                    self.play_role_list[key] = f.read()
    
    @property
    def default_play_role(self) -> str:
        """获取默认扮演角色"""
        return self._default_play_role
    
    @default_play_role.setter
    def default_play_role(self, value: str) -> None:
        """设置默认扮演角色"""
        self._default_play_role = value
        
        
        
# if __name__ == "__main__":
#     async def my_main():
#         ACM = ai_chat_manager("ATRI")
#         print(ACM.play_role_list["ATRI"])
#         await ACM.store_group_chat(123456,["aaaaaa","bbbbb"])
#         print(await ACM.get_group_chat(123456))
#         await ACM.store_group_chat(123456,[])
#         print(await ACM.reset_group_chat(123456))
#         await ACM.set_group_role(123456,"文言文版")
#         await ACM.reset_group_chat(123456)
#         print(await ACM.get_group_chat(123456))
    
#     asyncio.run(my_main())
