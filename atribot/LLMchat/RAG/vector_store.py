from abc import ABC, abstractmethod
from atribot.core.service_container import container
from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from logging import Logger
from typing import List




class VectorStoreBasics(ABC):
    """向量存查的基类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.vector_database:atriAsyncPostgreSQL = container.get("database")
        
    @abstractmethod
    async def storage(self,
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
    async def query_vector(
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
        
    async def storage(self,
        group_id:int|None, 
        user_id:int|None, 
        event_time:int,
        event:str,
        event_vector:List[float]
    )->None:
        sql = """
        INSERT INTO atri_memory 
            (group_id, user_id, event_time, event, event_vector) 
        VALUES 
            ($1, $2, $3, $4, $5)
        """
        await self.vector_database.execute_SQL(
            sql = sql,
            argument = (group_id, user_id, event_time, event, event_vector)
        )
        
    async def query_vector(
        self, 
        event_vector: List[float],
        limit: int = 5, 
        pattern: str = "<=>",
        group_id: int = None,
        user_id: int = None,
        start_time: int = None,
        end_time: int = None,
        include_distance: bool = False
    ) -> List[tuple]:
        """向量相似度查询
            • <-> - L2距离
            • <#> - （负）内积
            • <=> - 余弦距离
            • <+> - L1距离
            • <~> - 汉明距离（二进制向量）
            • <%> - 杰卡德距离（二进制向量）
            
        Args:
            event_vector: 查询向量
            limit: 返回结果数量,默认5
            pattern: 距离度量方式，支持 <=> | <-> | <#> | <+>
            group_id: 按群组过滤
            user_id: 按用户过滤
            start_time: 时间范围起点
            end_time: 时间范围终点
            include_distance:是否也返回向量字段
            
        Returns:
            查询结果列表
        """
        
        DISTANCE_CONFIG = {
            "<=>": ("余弦距离", "ASC"),
            "<->": ("欧氏距离", "ASC"),
            "<#>": ("负内积", "ASC"),
            "<+>": ("曼哈顿距离", "ASC")
        }
        
        if pattern not in DISTANCE_CONFIG:
            pattern = "<=>"
        
        # 动态构建条件和参数
        conditions = []
        params = [str(event_vector)]
        
        if group_id is not None:
            conditions.append(f"group_id = ${len(params) + 1}")
            params.append(group_id)
        
        if user_id is not None:
            conditions.append(f"user_id = ${len(params) + 1}")
            params.append(user_id)
        
        if start_time is not None:
            conditions.append(f"event_time >= ${len(params) + 1}")
            params.append(start_time)
        
        if end_time is not None:
            conditions.append(f"event_time <= ${len(params) + 1}")
            params.append(end_time)
        
        # 只查询非NULL的向量
        conditions.append("event_vector IS NOT NULL")
        
        params.append(limit)
        limit_param = len(params)
        
        where_clause = " AND ".join(conditions)
        
        if include_distance:
            sql = f"""
            SELECT 
                group_id,
                user_id,
                event_time,
                event,
                event_vector {pattern} $1::vector(1024) as distance,
                created_at
            FROM atri_memory
            WHERE {where_clause}
            ORDER BY distance ASC
            LIMIT ${limit_param}
            """
        else:
            sql = f"""
            SELECT 
                group_id,
                user_id,
                event_time,
                event,
                created_at
            FROM atri_memory
            WHERE {where_clause}
            ORDER BY event_vector {pattern} $1::vector(1024) ASC
            LIMIT ${limit_param}
            """
        
        return await self.vector_database.execute_SQL(
            sql=sql,
            argument=tuple(params)
        )
    
    async def add_to_knowledge_base(self, text_list:List[str], embedding_list:List[List[float]]):
        """把数据批量存储到知识库

        Args:
            text_list (List[str]): 文本
            embedding_list (List[List[float]]): 文本对应向量
        """
        import time
        sql = """
            INSERT INTO atri_memory (group_id, user_id, event_time, event, event_vector)
            VALUES (NULL, NULL, $1, $2, $3)
        """
        args_list = [
            (int(time.time()), text, emb)
            for text, emb in zip(text_list, embedding_list)
        ]
        async with self.vector_database as db:
            await db.executemany_with_pool(sql, args_list)

    async def add_user(self, text_list:List[str], embedding_list:List[List[float]], user_id:int|str, event_time:int):
        """存储用户消息

        Args:
            text_list (List[str]): 文本
            embedding_list (List[List[float]]): 文本对应向量
            user_id (int|str): 用户ID
            event_time (int): 记忆时间戳
        """
        sql = """
            INSERT INTO atri_memory (group_id, user_id, event_time, event, event_vector)
            VALUES ($1, $2, $3, $4, $5)
        """
        args_list = [
            (0, user_id, event_time, text, emb)
            for text, emb in zip(text_list, embedding_list)
        ]
        async with self.vector_database as db:
            await db.executemany_with_pool(sql, args_list)