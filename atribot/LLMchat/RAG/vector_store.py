from abc import ABC, abstractmethod
from atribot.core.service_container import container
from atribot.core.db.async_db_basics import AsyncDatabaseBase
from logging import Logger
from typing import List




class VectorStoreBasics(ABC):
    """向量存查的基类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.vector_database:AsyncDatabaseBase = container.get("database")
        
    @abstractmethod
    def storage(self,
        group_id:int|None, 
        user_id:int|None, 
        event_time:int,
        event:str,
        event_vector:List[float]
    )->None:
        """存储向量

        Args:
            group_id (int | None): 群号,0表示私聊,为0时user_id不能为空
            user_id (int | None): 账号唯一标识,和group_id一起为NULL表示知识库记忆
            event_time (int): 时间戳
            event (str): 文本
            event_vector (List[float]): 文本向量
        """
        pass
    
    @abstractmethod
    def query_vector(
        self, 
        event_vector:List[float], 
        limit:int=5, 
        pattern:str="余弦距离"
    )->List[tuple]:
        """简单不带条件在所有向量里查询

        Args:
            event_vector (List[float]): 向量
            limit (int, optional): 返回前几个. Defaults to 5.
            pattern (str, optional): 查询方法,支持:\n余弦距离,欧氏距离,曼哈顿距离,负内积. \nDefaults to "余弦距离".

        Returns:
            List[tuple]: 值
        """
        pass
    
    
    
    
class VectorStore(VectorStoreBasics):
    
    def __init__(self):
        super().__init__()