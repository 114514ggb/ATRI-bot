from collections import defaultdict, deque
from typing import Dict, List, Deque
import asyncio


class message_cache:
    """近期接收消息缓存(异步安全)"""
    
    def __init__(
        self,
        group_messages_upper_limit: int = 20,
        private_messages_upper_limit: int = 20
    ):
        self.group_messages: Dict[int, Deque[dict]] = defaultdict(
            lambda: deque(maxlen=group_messages_upper_limit)
        )
        self.private_messages: Dict[int, Deque[dict]] = defaultdict(
            lambda: deque(maxlen=private_messages_upper_limit)
        )
        self.group_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.private_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def get_group_messages(self, group_id: int) -> List[dict]:
        """返回群消息"""
        async with self.group_locks[group_id]:
            return list(self.group_messages[group_id])
    
    async def _set_group_messages(self, group_id: int, message: dict|str):
        """添加群消息"""
        async with self.group_locks[group_id]:
            self.group_messages[group_id].append(message)
    
    async def get_private_messages(self, user_id: int) -> List[dict]:
        """返回私聊消息"""
        async with self.private_locks[user_id]:
            return list(self.private_messages[user_id])
    
    async def _set_private_messages(self, user_id: int, message: dict|str):
        """添加私聊消息"""
        async with self.private_locks[user_id]:
            self.private_messages[user_id].append(message)
    
    async def cache_system(self,data:dict,message_test:str):
        """存储消息"""
        
        if message_type := data.get("message_type",False): 
            #是带消息的dict
            
            if message_type == 'group':
                
                await self._set_group_messages(
                    data['group_id'],
                    f"{data['user_id']}|{data['sender']['nickname']}发送:{message_test}"
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

# async def main():
#     mc = MessageCache()
#     group = 123456
#     for n in range(0,30):
#         await mc._set_group_messages(group,str(n)+"消息")
        
#     print(await mc.get_group_messages(group))

# if __name__ == "__main__":
#     asyncio.run(main())
        