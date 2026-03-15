import time
from abc import ABC, abstractmethod
from logging import Logger
from typing import Any, List, Literal

from asyncpg import Record

from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from atribot.core.service_container import container

MemoryCategory = Literal[
    "preference",   # 用户偏好
    "fact",         # 事实性记忆(默认)
    "experience",   # 经历记忆
    "emotion",      # 情感记忆
    "group_topic",  # 群聊话题或群体共识
    "knowledge",    # 通用知识条目
    "domain",       # 领域专业知识
    "guideline",    # 行为准则知识
]


class VectorStoreBasics(ABC):
    """向量存查的基类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.vector_database:atriAsyncPostgreSQL = container.get("database")
        
    @abstractmethod
    async def storage(self)->None:
        """存储到记忆表"""
        pass
    
    @abstractmethod
    async def batch_add_memories(self):
        """批量存储到记忆表"""
        pass
    
    @abstractmethod
    async def query_memories(self):
        """查询的方法"""
        pass


class MemoryVectorStore(VectorStoreBasics):
    """向量数据库面向记忆的接口"""

    def __init__(self):
        super().__init__()

    async def storage(
        self,
        group_id: int | None,
        user_id: int | None,
        event_time: int,
        event: str,
        event_vector: str,
        *,
        category: MemoryCategory = "fact",
        importance: int = 5,
        credibility: int = 5,
    ) -> None:
        """存储单条记忆

        Args:
            group_id: 群组ID,None=知识库,0=私聊,正整数=群聊
            user_id:  用户ID,None=知识库
            event_time: 事件发生时间(Unix 时间戳,秒)
            event:      记忆文本
            event_vector: 1024 维语义向量
            category:   记忆类型,默认 'fact'
            importance: 重要度 1~10,默认 5
            credibility: 可信度 1~10,默认 5
        """
        sql = """
        INSERT INTO atri_memory
            (user_id, group_id, event_time, event, event_vector,
             category, importance, credibility)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        await self.vector_database.execute_SQL(
            sql=sql,
            argument=(user_id, group_id, event_time, event, event_vector,
                      category, importance, credibility),
        )

    async def batch_add_memories(self, args_list: List[tuple]) -> None:
        """批量插入记忆,冲突时跳过(uq_user_event_hash)

        每条 tuple 必须为完整格式：
            (user_id, group_id, event_time, event, event_vector,
             category, importance, credibility)

        Args:
            args_list: 包含记忆数据的元组列表
        """
        if not args_list:
            return

        sql = """
            INSERT INTO atri_memory
                (user_id, group_id, event_time, event, event_vector,
                 category, importance, credibility)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id, event) DO NOTHING;
        """

        async with self.vector_database as db:
            await db.executemany_with_pool(sql, args_list)

    async def add_memory(self, args: tuple) -> None:
        """插入单条记忆,不做冲突处理

        tuple 必须为完整格式：
            (user_id, group_id, event_time, event, event_vector,
             category, importance, credibility)

        Args:
            args: 包含记忆数据的元组
        """
        sql = """
            INSERT INTO atri_memory
                (user_id, group_id, event_time, event, event_vector,
                 category, importance, credibility)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        async with self.vector_database as db:
            await db.execute_with_pool(sql, args)

    async def add_to_knowledge_base(
        self,
        text_list: List[str],
        embedding_list: List[List[float]],
        *,
        category: MemoryCategory = "knowledge",
        importance: int = 5,
        credibility: int = 8,
    ) -> None:
        """批量存储条目到知识库(user_id=NULL, group_id=NULL)

        Args:
            text_list:       文本列表
            embedding_list:  对应向量列表
            category:        默认 'knowledge'
            importance:      默认 5
            credibility:     知识库通常可信度较高,默认 8
        """
        sql = """
            INSERT INTO atri_memory
                (user_id, group_id, event_time, event, event_vector,
                 category, importance, credibility)
            VALUES (NULL, NULL, $1, $2, $3, $4, $5, $6)
        """
        new_time = int(time.time())
        args = [
            (new_time, text, emb, category, importance, credibility)
            for text, emb in zip(text_list, embedding_list)
        ]
        async with self.vector_database as db:
            await db.executemany_with_pool(sql, args)

    async def update_access_stats(self, memory_id: int) -> None:
        """命中记忆后更新访问次数与最后访问时间

        Args:
            memory_id: 被检索到的 memory_id
        """
        sql = """
            UPDATE atri_memory
            SET access_count = access_count + 1,
                last_accessed = EXTRACT(EPOCH FROM NOW())::bigint
            WHERE memory_id = $1
        """
        async with self.vector_database as db:
            await db.execute_with_pool(sql, (memory_id,))

    async def batch_update_access_stats(self, memory_ids: List[int]) -> None:
        """批量更新命中记忆的访问统计

        Args:
            memory_ids: memory_id 列表
        """
        if not memory_ids:
            return
        sql = """
            UPDATE atri_memory
            SET access_count = access_count + 1,
                last_accessed = EXTRACT(EPOCH FROM NOW())::bigint
            WHERE memory_id = ANY($1::bigint[])
        """
        async with self.vector_database as db:
            await db.execute_with_pool(sql, (memory_ids,))


    async def query_memories(
        self,
        query_vector: List[float]|str = None,
        limit: int = 5,
        group_id: int | str = None,
        user_id: int | str = None,
        start_time: int | str = None,
        end_time: int | str = None,
        exclude_knowledge_base: bool = False,
        only_knowledge_base: bool = False,
        distance_threshold: float = 0.5,
        *,
        category: MemoryCategory | None = None,
        min_importance: int | None = None,
        min_credibility: int | None = None,
        update_stats: bool = False,
    ) -> list[Record] | Record:
        """通用向量查询接口

        Args:
            query_vector:     查询向量(1024 维)如果为 None,则按创建时间倒序返回
            limit:            返回结果数量限制,默认 5
            group_id:         群组 ID 筛选(None 表示不筛选,0 表示私聊,正数表示群聊)
            user_id:          用户 ID 筛选(None 表示不筛选)
            start_time:       事件开始时间戳(秒,包含)
            end_time:         事件结束时间戳(秒,包含)
            exclude_knowledge_base: 是否排除知识库记忆
            only_knowledge_base: 是否只查询知识库记忆
            distance_threshold: 向量距离阈值,仅在提供 `query_vector` 时生效
                               只返回余弦距离(<=>)小于等于此值的结果,默认 0.5
            category:         记忆类型过滤(例如 'fact', 'preference' 等)
            min_importance:   最低重要度过滤(1~10)
            min_credibility:  最低可信度过滤(1~10)
            update_stats:     查询命中后是否自动更新命中记忆的访问统计

        Returns:
            记忆记录字典列表如果提供了 `query_vector`,则按距离升序排列；
            否则按 `created_at` 降序排列
            每条记录包含：memory_id, user_id, group_id, event_time, event,
                         created_at, category, importance, credibility,
                         access_count, distance
        """
        where_clauses: List[str] = []
        params: List[Any] = []
        idx = 1  # $n 占位符计数

        if only_knowledge_base:
            where_clauses.append("user_id IS NULL AND group_id IS NULL")
        elif exclude_knowledge_base:
            where_clauses.append("NOT (user_id IS NULL AND group_id IS NULL)")

        if group_id is not None:
            where_clauses.append(f"group_id = ${idx}")
            params.append(group_id)
            idx += 1
        if user_id is not None:
            where_clauses.append(f"user_id = ${idx}")
            params.append(user_id)
            idx += 1
        if start_time is not None:
            where_clauses.append(f"event_time >= ${idx}")
            params.append(start_time)
            idx += 1
        if end_time is not None:
            where_clauses.append(f"event_time <= ${idx}")
            params.append(end_time)
            idx += 1

        if category is not None:
            where_clauses.append(f"category = ${idx}::memory_category")
            params.append(category)
            idx += 1
        if min_importance is not None:
            where_clauses.append(f"importance >= ${idx}")
            params.append(min_importance)
            idx += 1
        if min_credibility is not None:
            where_clauses.append(f"credibility >= ${idx}")
            params.append(min_credibility)
            idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        if query_vector is not None:
            vec_param = f"${idx}"
            params.append(str(query_vector))
            idx += 1

            distance_expr = f"event_vector <=> {vec_param}::vector(1024)"
            select_distance = f"{distance_expr} AS distance"
            order_by = "distance ASC"

            if distance_threshold is not None:
                where_sql += f" AND {distance_expr} <= ${idx}"
                params.append(distance_threshold)
                idx += 1
        else:
            select_distance = "0.0 AS distance"
            order_by = "created_at DESC"

        params.append(limit)

        sql = f"""
            SELECT
                memory_id,
                user_id,
                group_id,
                event_time,
                event,
                created_at,
                category,
                importance,
                credibility,
                access_count,
                {select_distance}
            FROM atri_memory
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${idx}
        """

        rows = await self.vector_database.execute_SQL(
            sql=sql,
            argument=tuple(params),
        )

        if update_stats and rows:
            ids = [r["memory_id"] for r in rows if r.get("memory_id")]
            if ids:
                await self.batch_update_access_stats(ids)

        return rows

    async def query_by_category(
        self,
        category: MemoryCategory,
        query_vector: List[float] = None,
        limit: int = 10,
        user_id: int | None = None,
        group_id: int | None = None,
        distance_threshold: float = 0.5,
    ) -> list[Record] | Record:
        """按记忆类型查询

        Args:
            category:          记忆类型,见 MemoryCategory
            query_vector:      可选,提供时按向量相似度排序
            limit:             返回数量上限
            user_id / group_id: 可选过滤
            distance_threshold: 向量距离阈值
        """
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            user_id=user_id,
            group_id=group_id,
            distance_threshold=distance_threshold,
            category=category,
        )

    async def query_important_memories(
        self,
        query_vector: List[float]|str= None,
        limit: int = 10,
        min_importance: int = 7,
        user_id: int | None = None,
        group_id: int | None = None,
        distance_threshold: float = 0.5,
    ) -> list[Record] | Record:
        """查询高重要度记忆(importance >= min_importance)

        Args:
            min_importance: 最低重要度,默认 7(重要个人信息)
        """
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            user_id=user_id,
            group_id=group_id,
            distance_threshold=distance_threshold,
            min_importance=min_importance,
        )

    async def query_private_chat(
        self,
        query_vector: List[float]|str,
        user_id: int,
        limit: int = 10,
        start_time: int | str = None,
        end_time: int | str = None,
        category: MemoryCategory | None = None,
    ) -> list[Record] | Record:
        """查询私聊记忆(group_id = 0)

        Args:
            query_vector: 查询向量
            user_id: 用户 ID
            limit: 返回结果数量上限
            start_time: 开始时间戳过滤
            end_time: 结束时间戳过滤
            category: 记忆类型过滤

        Returns:
            符合条件的私聊记忆列表
        """
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            group_id=0,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            category=category,
        )

    async def query_group_chat(
        self,
        query_vector: List[float]|str,
        group_id: int,
        limit: int = 10,
        user_id: int | str = None,
        start_time: int | str = None,
        end_time: int | str = None,
        category: MemoryCategory | None = None,
    ) -> list[Record] | Record:
        """查询群聊记忆(group_id 为正整数)

        Args:
            query_vector: 查询向量
            group_id: 群组 ID(非 0)
            limit: 返回结果数量上限
            user_id: 可选的用户 ID 筛选
            start_time: 开始时间戳过滤
            end_time: 结束时间戳过滤
            category: 记忆类型过滤

        Returns:
            符合条件的群聊记忆列表

        Raises:
            ValueError: 如果 group_id 为 0
        """
        if group_id == 0:
            raise ValueError("群聊的 group_id 不能 为 0,请使用 query_private_chat 查询私聊")
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            group_id=group_id,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            category=category,
        )

    async def query_knowledge_base(
        self,
        query_vector: List[float]|str,
        limit: int = 10,
        distance_threshold: float = None,
        category: MemoryCategory | None = None,
        min_importance: int | None = None,
    ) -> list[Record] | Record:
        """查询知识库记忆(user_id IS NULL AND group_id IS NULL)

        Args:
            query_vector: 查询向量
            limit: 返回结果数量上限
            distance_threshold: 向量距离阈值
            category: 可选,只返回指定类型的知识库条目
            min_importance: 可选,最低重要度过滤

        Returns:
            符合条件的知识库记忆列表
        """
        return await self.query_memories(
            query_vector=query_vector,
            limit=limit,
            only_knowledge_base=True,
            distance_threshold=distance_threshold,
            category=category,
            min_importance=min_importance,
        )