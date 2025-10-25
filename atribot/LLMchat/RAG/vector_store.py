from abc import ABC, abstractmethod
from atribot.core.service_container import container
from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from logging import Logger
from typing import List, Dict, Any




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
    """管理向量数据库的一些查询"""
    
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
            AND event_vector {pattern} $1::vector(1024) <= 0.5
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
            AND event_vector {pattern} $1::vector(1024) <= 0.5
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
        new_time = int(time.time())
        args_list = [
            (new_time, text, emb)
            for text, emb in zip(text_list, embedding_list)
        ]
        async with self.vector_database as db:
            await db.executemany_with_pool(sql, args_list)

            
    async def batch_add_memories(self, args_list:List[tuple]):
        """批量插入user消息

        Args:
            args_list (List[tuple]): 插入tuple
        """
        sql = """
            INSERT INTO atri_memory (group_id, user_id, event_time, event, event_vector)
            VALUES ($1, $2, $3, $4, $5)
        """
        async with self.vector_database as db:
            await db.executemany_with_pool(sql, args_list)

    
    async def query_memories(
        self,
        query_vector: List[float],
        limit: int = 5,
        group_id: int|str = None,
        user_id: int|str = None,
        start_time: int|str = None,
        end_time: int|str = None,
        exclude_knowledge_base: bool = False,
        only_knowledge_base: bool = False,
        distance_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        通用向量查询接口
        
        Args:
            query_vector: 查询向量 (1024维)
            limit: 返回结果数量限制
            group_id: 群组ID筛选 (None表示不筛选)
            user_id: 用户ID筛选 (None表示不筛选)
            start_time: 开始时间戳 (包含)
            end_time: 结束时间戳 (包含)
            exclude_knowledge_base: 排除知识库记忆 (group_id和user_id都为NULL的记录)
            only_knowledge_base: 只查询知识库记忆
            distance_threshold: 向量距离阈值,只返回距离小于等于此值的结果,默认小于0.5
        
        Returns:
            记忆记录列表,按向量相似度排序
        """
        # 构建WHERE子句
        where_clauses = []
        params = []
        param_index = 1
        
        # 处理知识库记忆筛选
        if only_knowledge_base:
            where_clauses.append("group_id IS NULL AND user_id IS NULL")
        elif exclude_knowledge_base:
            where_clauses.append("NOT (group_id IS NULL AND user_id IS NULL)")
        
        # group_id筛选
        if group_id is not None:
            where_clauses.append(f"group_id = ${param_index}")
            params.append(group_id)
            param_index += 1
        
        # user_id筛选
        if user_id is not None:
            where_clauses.append(f"user_id = ${param_index}")
            params.append(user_id)
            param_index += 1
        
        # 时间范围筛选
        if start_time is not None:
            where_clauses.append(f"event_time >= ${param_index}")
            params.append(start_time)
            param_index += 1
        
        if end_time is not None:
            where_clauses.append(f"event_time <= ${param_index}")
            params.append(end_time)
            param_index += 1
        
        # 构建基础SQL
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        # 向量查询子句
        vector_param = f"${param_index}"
        params.append(query_vector)
        param_index += 1
        
        # 构建完整SQL
        sql = f"""
            SELECT 
                memory_id,
                group_id,
                user_id,
                event_time,
                event,
                created_at,
                event_vector <=> {vector_param}::vector(1024) AS distance
            FROM atri_memory
            WHERE {where_sql}
        """
        
        # 添加距离阈值筛选
        if distance_threshold is not None:
            sql += f" AND event_vector <=> {vector_param}::vector(1024) <= ${param_index}"
            params.append(distance_threshold)
            param_index += 1
        
        # 排序和限制
        sql += f"""
            ORDER BY distance ASC
            LIMIT ${param_index}
        """
        params.append(limit)
        
        # 执行查询
        results = await self.vector_database.execute_SQL(
            sql=sql,
            argument=tuple(params)
        )
        
        return results
    
    async def query_private_chat(
        self,
        query_vector: List[float],
        user_id: int,
        limit: int = 10,
        start_time: int|str = None,
        end_time: int|str = None
    ) -> List[Dict[str, Any]]:
        """
        查询私聊记忆 (group_id=0)
        
        参数:
            query_vector: 查询向量
            user_id: 用户ID
            limit: 返回结果数量
            start_time: 开始时间戳
            end_time: 结束时间戳
        """
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            group_id=0,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time
        )
    
    async def query_group_chat(
        self,
        query_vector: List[float],
        group_id: int,
        limit: int = 10,
        user_id: int|str = None,
        start_time: int|str = None,
        end_time: int|str = None
    ) -> List[Dict[str, Any]]:
        """
        查询群聊记忆
        
        参数:
            query_vector: 查询向量
            group_id: 群组ID (非0)
            limit: 返回结果数量
            user_id: 可选的用户ID筛选
            start_time: 开始时间戳
            end_time: 结束时间戳
        """
        if group_id == 0:
            raise ValueError("群聊的group_id不能为0,请使用query_private_chat查询私聊")
        
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            group_id=group_id,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time
        )
    
    async def query_knowledge_base(
        self,
        query_vector: List[float],
        limit: int = 10,
        distance_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        查询知识库记忆 (group_id和user_id都为NULL)
        
        参数:
            query_vector: 查询向量
            limit: 返回结果数量
            distance_threshold: 距离阈值
        """
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            only_knowledge_base=True,
            distance_threshold=distance_threshold
        )