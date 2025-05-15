import asyncio
from typing import Dict, List

class MessageCache:
    """近期接收消息缓存(异步安全)"""
    
    def __init__(
        self,
        group_messages_upper_limit: int = 20,
        private_messages_upper_limit: int = 20
    ):
        self.group_messages: Dict[int, List[dict]] = {}
        """群消息"""
        self.private_messages: Dict[int, List[dict]] = {}
        """私聊消息"""
        self.group_messages_upper_limit = group_messages_upper_limit
        self.private_messages_upper_limit = private_messages_upper_limit
        self.group_locks: Dict[int, asyncio.Lock] = {}
        self.private_locks: Dict[int, asyncio.Lock] = {}
    
    async def get_group_messages(self, group_id: int) -> List[dict]:
        """返回群消息"""
        if group_id not in self.group_locks:
            self.group_locks[group_id] = asyncio.Lock()
        
        async with self.group_locks[group_id]:
            return self.group_messages.get(group_id, []).copy()
    
    async def _set_group_messages(self, group_id: int, message: dict):
        """添加群消息"""
        if group_id not in self.group_locks:
            self.group_locks[group_id] = asyncio.Lock()
        
        async with self.group_locks[group_id]:
            if group_id not in self.group_messages:
                self.group_messages[group_id] = []
            
            self.group_messages[group_id].append(message)
            
            if len(self.group_messages[group_id]) > self.group_messages_upper_limit:
                self.group_messages[group_id].pop(0)
    
    async def get_private_messages(self, user_id: int) -> List[dict]:
        """返回私聊消息"""
        if user_id not in self.private_locks:
            self.private_locks[user_id] = asyncio.Lock()
        
        async with self.private_locks[user_id]:
            return self.private_messages.get(user_id, []).copy()
    
    async def _set_private_messages(self, user_id: int, message: dict):
        """添加私聊消息"""
        if user_id not in self.private_locks:
            self.private_locks[user_id] = asyncio.Lock()
        
        async with self.private_locks[user_id]:
            if user_id not in self.private_messages:
                self.private_messages[user_id] = []
            
            self.private_messages[user_id].append(message)
            
            if len(self.private_messages[user_id]) > self.private_messages_upper_limit:
                self.private_messages[user_id].pop(0)
    
    async def cache_system(self,data:dict,message_test:str):
        """存储消息"""
        
        if message_type := data.get("message_type",False): 
            #是带消息的dict
            
            if message_type == 'group':
                await self._set_group_messages(
                    data['group_id'],
                    message_test
                )
                return None
            
            elif message_type == 'private':
                await self._set_private_messages(
                    data['sender']['user_id'],
                    message_test
                )
                return None
        
        else:
            #应该基本都是非聊天事件
            pass


# if __name__ == "__main__":
#     mc = MessageCache()
#     for n in 