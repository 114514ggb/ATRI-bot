from logging import Logger
from typing import Any, Dict, List, Optional, Tuple

from asyncpg import Record

from atribot.core.service_container import container
from atribot.LLMchat.RAG.rag import RAGManager
from atribot.LLMchat.RAG.vector_store import MemoryCategory


class MemoryRetriever:
    """记忆检索器:执行复杂的SQL检索和混合召回"""

    def __init__(self, rag: RAGManager):
        self.log: Logger = container.get_by_type(Logger).getChild("Memory.Ret")
        self.rag = rag
        self.vector_store = rag.vector_store

    async def query_similarity_edges_grouped(
        self, 
        start_time: int, 
        threshold: float, 
        min_cluster_size: int
    ) -> Dict[Tuple[int, str], List[Tuple[int, int]]]:
        """按(user_id, category)分组查询两两相似边"""
        sql = """
            WITH candidates AS (
                SELECT
                    memory_id,
                    user_id,
                    category,
                    event_vector,
                    event
                FROM atri_memory
                WHERE created_at >= $1
                  AND user_id IS NOT NULL
                  AND event_vector IS NOT NULL
                  AND event IS NOT NULL
                  AND LENGTH(TRIM(event)) > 0
            ), valid_groups AS (
                SELECT user_id, category
                FROM candidates
                GROUP BY user_id, category
                HAVING COUNT(*) >= $3
            )
            SELECT
                a.memory_id AS memory_id_a,
                b.memory_id AS memory_id_b,
                a.user_id,
                a.category
            FROM candidates a
            JOIN valid_groups g
                ON a.user_id IS NOT DISTINCT FROM g.user_id
               AND a.category = g.category
            JOIN candidates b
                ON a.memory_id < b.memory_id
               AND a.user_id IS NOT DISTINCT FROM b.user_id
               AND a.category = b.category
            WHERE (a.event_vector <=> b.event_vector) <= $2
        """
        async with self.vector_store.vector_database as db:
            rows = await db.execute_with_pool(
                sql, (start_time, threshold, min_cluster_size), fetch_type="all"
            )

        grouped_edges: Dict[Tuple[int, str], List[Tuple[int, int]]] = {}
        for row in rows or []:
            grouped_edges.setdefault((row["user_id"], row["category"]), []).append(
                (row["memory_id_a"], row["memory_id_b"])
            )
        return grouped_edges
   
    async def query_recently_memory(self, text:str, limit:int = 5)->list[Record]:
        """简单根据文本向量查询数据库最相似消息,返回余弦距离<0.5,和最近30天内的消息

        Args:
            text (str): 要文本搜索的文本,太长会截取
            limit (int): 返回最大数量

        Returns:
            list[Record]: 返回查询到的表行最多limit条,
                每条包含: user_id, group_id, event_time, event, category, importance, credibility
        """
        if embeddin_list := await self.rag.calculate_embedding(text[:500]):

            sql = """
            SELECT
                user_id,
                group_id,
                event_time,
                event,
                credibility,
                (event_vector <=> $1::vector(1024)) AS distance
            FROM atri_memory
            WHERE (event_vector <=> $1::vector(1024)) <= 0.5
            AND event_time >= EXTRACT(EPOCH FROM (NOW() - INTERVAL '30 days'))::bigint
            ORDER BY distance ASC
            LIMIT $2
            """

            async with self.vector_store.vector_database as db:
                return await db.execute_with_pool(
                    query = sql,
                    params = (str(embeddin_list), limit),
                    fetch_type = "all"
                )

        return []

    async def query_user_recently_memory(self, user_id:int, text:str, limit:int = 5)->list[Record]:
        """简单根据文本向量查询数据库user最相似消息,返回余弦距离<0.5,和最近30天内的消息

        Args:

            text (str): 要文本搜索的文本,太长会截取
            limit (int): 返回最大数量

        Returns:
            list[Record]: 返回查询到的表行最多limit条,
                每条包含: user_id, group_id, event_time, event, category, importance, credibility
        """
        if embeddin_list := await self.rag.calculate_embedding(text[:500]):

            sql = """
            SELECT
                user_id,
                group_id,
                event_time,
                event,
                credibility,
                (event_vector <=> $1::vector(1024)) AS distance
            FROM atri_memory
            WHERE (event_vector <=> $1::vector(1024)) <= 0.5
            AND user_id = $2
            AND event_time >= EXTRACT(EPOCH FROM (NOW() - INTERVAL '30 days'))::bigint
            ORDER BY distance ASC
            LIMIT $3
            """

            async with self.vector_store.vector_database as db:
                return await db.execute_with_pool(
                    query = sql,
                    params = (str(embeddin_list), user_id, limit),
                    fetch_type = "all"
                )

        return []

    async def query_memories(
        self,
        query_text: str = None,
        limit: int = 5,
        group_id: int|str = None,
        user_id: int|str = None,
        start_time: int|str = None,
        end_time: int|str = None,
        exclude_knowledge_base: bool = False,
        only_knowledge_base: bool = False,
        distance_threshold: float = 0.5,
        *,
        category: Optional[MemoryCategory] = None,
        min_importance: Optional[int] = None,
        min_credibility: Optional[int] = None,
        update_stats: bool = False,
    ) -> list[Record]:
        """
        通用向量查询接口

        Args:
            query_text: 要查询的文本,会转换成向量。如果其值为假则按创建时间倒序返回
            limit: 返回结果数量限制
            group_id: 群组ID筛选 (None不筛选, 0=私聊, 正整数=群聊)
            user_id: 用户ID筛选 (None表示不筛选)
            start_time: 开始时间戳 (包含)
            end_time: 结束时间戳 (包含)
            exclude_knowledge_base: 排除知识库记忆 (group_id和user_id都为NULL的记录)
            only_knowledge_base: 只查询知识库记忆
            distance_threshold: 向量距离阈值,只返回距离小于等于此值的结果,默认0.5
            category: 记忆类型过滤,None不过滤
            min_importance: 最低重要度过滤 (1~10)
            min_credibility: 最低可信度过滤 (1~10)
            update_stats: 是否自动更新命中记忆的访问统计,默认False

        Returns:
            记忆记录字典列表,提供query_text时按向量相似度升序,否则按created_at降序
            每条包含: memory_id, user_id, group_id, event_time, event,
                      created_at, category, importance, credibility, access_count, distance
        """

        return await self.vector_store.query_memories(
            await self.rag.calculate_embedding(query_text) if query_text else None,
            limit,
            group_id,
            user_id,
            start_time,
            end_time,
            exclude_knowledge_base,
            only_knowledge_base,
            distance_threshold,
            category=category,
            min_importance=min_importance,
            min_credibility=min_credibility,
            update_stats=update_stats,
        )

    async def hybrid_recall(
        self,
        query_text: str,
        *,
        limit: int = 10,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        category: Optional[MemoryCategory] = None,
        min_importance: int = 1,
        min_credibility: int = 1,
        only_knowledge_base: bool = False,
        exclude_knowledge_base: bool = False,
        vector_distance_threshold: float = 0.5,
        vector_candidates: int = 40,
        fulltext_candidates: int = 40,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        fulltext_weight: float = 1.0,
        importance_weight: float = 0.4,
        access_weight: float = 0.1,
        time_decay_weight: float = 0.3,
        update_stats: bool = False,
    ) -> list[Record]:
        """根据向量和全文进行混合召回,融合时间衰减评分最后返回记忆list

        用一条带 CTE 的 SQL 完成两路召回 → ROW_NUMBER() 排名 → RRF 计分 →
        FULL OUTER JOIN 合并 → 叠加 importance/access_count/时间衰减 附加分 → 排序截断

        SQL 结构(CTE 链):
            vec_ranked   — 向量路按距离升序,取 vector_candidates 候选,附带行号
            ft_ranked    — 全文路按 pgroonga_score 降序,取 fulltext_candidates 候选,附带行号
            merged       — FULL OUTER JOIN,COALESCE 取非 NULL 的基础字段
            scored       — 计算 hybrid_score:
                             $vector_weight  / (rrf_k + vec_rank)   向量 RRF 贡献,无命中则 0
                           + $fulltext_weight / (rrf_k + ft_rank)   全文 RRF 贡献,无命中则 0
                           + $importance_weight * (importance / 10.0)
                           + $access_weight    * ln(1 + access_count)
                           + $time_decay_weight * EXP(-λ * age_days)  时间衰减贡献
                             λ 按 category 差异化:
                               group_topic  → 半衰期 7  天  (λ ≈ 0.099)
                               emotion      → 半衰期 30 天  (λ ≈ 0.023)
                               experience   → 半衰期 60 天  (λ ≈ 0.012)
                               fact/preference → 半衰期 90 天 (λ ≈ 0.008)
                               knowledge/domain/guideline → 半衰期 3650 天 (λ ≈ 0.00019)
        最终按 hybrid_score DESC LIMIT $limit 返回

        Args:
            query_text:                查询文本
            limit:                     最终返回记忆条数,默认 10
            user_id:                   用户 ID 筛选,None 不筛选
            group_id:                  群组 ID 筛选,None 不筛选
            start_time:                事件时间下界(Unix 秒,包含)
            end_time:                  事件时间上界(Unix 秒,包含)
            category:                  记忆类型过滤,None 不过滤
            min_importance:            重要度下界(1~10),默认 1(不过滤)
            min_credibility:           可信度下界(1~10),默认 1(不过滤)
            only_knowledge_base:       仅查知识库(user_id IS NULL AND group_id IS NULL)
            exclude_knowledge_base:    排除知识库条目
            vector_distance_threshold: 向量余弦距离上限,默认 0.5
            vector_candidates:         向量路候选数,默认 40
            fulltext_candidates:       全文路候选数,默认 40
            rrf_k:                     RRF 平滑常数,默认 60
            vector_weight:             向量路 RRF 权重,默认 1.0
            fulltext_weight:           全文路 RRF 权重,默认 1.0
            importance_weight:         importance 附加权重,默认 0.4
            access_weight:             access_count 附加权重(log 平滑),默认 0.1
            time_decay_weight:         时间衰减项整体权重,默认 0.3;设为 0 可完全禁用
            update_stats:              是否自动更新命中记忆的 access_count / last_accessed

        Returns:
            按 hybrid_score 从高到低排列的记忆字典列表,每条包含：
                memory_id, user_id, group_id, event_time, event,
                created_at, category, importance, credibility,
                access_count, vec_distance, ft_score, hybrid_score
        """
        if not query_text or not query_text.strip():
            return []

        # 单条 str 输入返回单个向量(List[float]),直接作为查询向量使用
        query_vector = await self.rag.calculate_embedding(query_text)
        if not query_vector:
            return []

        filter_clauses: List[str] = []
        filter_params: List[Any] = []
        idx = 6 

        if only_knowledge_base:
            filter_clauses.append("user_id IS NULL AND group_id IS NULL")
        elif exclude_knowledge_base:
            filter_clauses.append("NOT (user_id IS NULL AND group_id IS NULL)")

        if group_id is not None:
            filter_clauses.append(f"group_id = ${idx}")
            filter_params.append(group_id)
            idx += 1
        if user_id is not None:
            filter_clauses.append(f"user_id = ${idx}")
            filter_params.append(user_id)
            idx += 1
        if start_time is not None:
            filter_clauses.append(f"event_time >= ${idx}")
            filter_params.append(start_time)
            idx += 1
        if end_time is not None:
            filter_clauses.append(f"event_time <= ${idx}")
            filter_params.append(end_time)
            idx += 1
        if category is not None:
            filter_clauses.append(f"category = ${idx}::memory_category")
            filter_params.append(category)
            idx += 1
        if min_importance > 1:
            filter_clauses.append(f"importance >= ${idx}")
            filter_params.append(min_importance)
            idx += 1
        if min_credibility > 1:
            filter_clauses.append(f"credibility >= ${idx}")
            filter_params.append(min_credibility)
            idx += 1

        vec_extra = "AND event_vector IS NOT NULL AND event_vector <=> $1::vector(1024) <= $3"
        ft_extra  = "AND event &@~ $2"

        filter_where = ("AND " + " AND ".join(filter_clauses)) if filter_clauses else ""

        limit_param = idx
        idx += 1


        #   $1 = query_vector (vector)
        #   $2 = fulltext_query (text)
        #   $3 = vector_distance_threshold (float8)
        #   $4 = vector_candidates (int)
        #   $5 = fulltext_candidates (int)
        params: tuple = (
            str(query_vector),         
            query_text[:200],           
            vector_distance_threshold, 
            vector_candidates,          
            fulltext_candidates,        
            *filter_params,             # $6 ~ $N
            limit,                      # $limit_param
        )
        
        sql = f"""
        WITH vec_ranked AS (
            -- 向量查询部分
            SELECT
                memory_id,
                user_id, group_id, event_time, event, created_at,
                category, importance, credibility, access_count,
                (event_vector <=> $1::vector(1024))          AS vec_distance,
                ROW_NUMBER() OVER (
                    ORDER BY event_vector <=> $1::vector(1024) ASC
                )                                            AS vec_rank
            FROM atri_memory
            WHERE TRUE
                {vec_extra}
                {filter_where}
            ORDER BY vec_distance ASC
            LIMIT $4
        ),
        ft_ranked AS (
            -- 全文搜索部分
            SELECT
                memory_id,
                user_id, group_id, event_time, event, created_at,
                category, importance, credibility, access_count,
                pgroonga_score(tableoid, ctid) AS ft_score,
                ROW_NUMBER() OVER (
                    ORDER BY pgroonga_score(tableoid, ctid) DESC
                )                              AS ft_rank
            FROM atri_memory
            WHERE TRUE
                {ft_extra}
                {filter_where}
            ORDER BY ft_score DESC
            LIMIT $5
        ),
        merged AS (
            -- FULL OUTER JOIN 合并两路结果
            SELECT
                COALESCE(v.memory_id,    f.memory_id)    AS memory_id,
                COALESCE(v.user_id,      f.user_id)      AS user_id,
                COALESCE(v.group_id,     f.group_id)     AS group_id,
                COALESCE(v.event_time,   f.event_time)   AS event_time,
                COALESCE(v.event,        f.event)        AS event,
                COALESCE(v.created_at,   f.created_at)   AS created_at,
                COALESCE(v.category,     f.category)     AS category,
                COALESCE(v.importance,   f.importance)   AS importance,
                COALESCE(v.credibility,  f.credibility)  AS credibility,
                COALESCE(v.access_count, f.access_count) AS access_count,
                v.vec_distance,
                v.vec_rank,
                f.ft_score,
                f.ft_rank
            FROM vec_ranked  v
            FULL OUTER JOIN ft_ranked f USING (memory_id)
        ),
        scored AS (
            -- RRF 融合 + 时间衰减
            SELECT
                memory_id, user_id, group_id, event_time, event,
                created_at, category, importance, credibility, access_count,
                vec_distance,
                ft_score,
                (
                    COALESCE({vector_weight}   / ({rrf_k} + vec_rank), 0)
                  + COALESCE({fulltext_weight} / ({rrf_k} + ft_rank),  0)
                  + {importance_weight} * (COALESCE(importance, 5) / 10.0)
                  + {access_weight}     * LN(1 + COALESCE(access_count, 0))
                  + {time_decay_weight} * EXP(
                        - CASE COALESCE(category::text, 'fact')
                            WHEN 'group_topic'  THEN 0.0990
                            WHEN 'emotion'      THEN 0.0231
                            WHEN 'experience'   THEN 0.0116
                            WHEN 'fact'         THEN 0.0077
                            WHEN 'preference'   THEN 0.0077
                            WHEN 'knowledge'    THEN 0.00019
                            WHEN 'domain'       THEN 0.00019
                            WHEN 'guideline'    THEN 0.00019
                            ELSE                     0.0077
                          END
                        * GREATEST(
                            (FLOOR(EXTRACT(EPOCH FROM NOW()))::bigint - COALESCE(event_time, created_at))
                            / 86400.0,
                            0
                          )
                    )
                )  AS hybrid_score
            FROM merged
        )
        SELECT *
        FROM scored
        ORDER BY hybrid_score DESC
        LIMIT ${limit_param}
        """

        try:
            async with self.vector_store.vector_database as db:
                rows = await db.execute_with_pool(sql, params, fetch_type="all")
        except Exception as e:
            self.log.error(f"hybrid_recall 混合查询失败,降级到纯向量: {e}")
            try:
                return await self.vector_store.query_memories(
                    query_vector=query_vector,
                    limit=limit,
                    user_id=user_id,
                    group_id=group_id,
                    start_time=start_time,
                    end_time=end_time,
                    category=category,
                    min_importance=min_importance if min_importance > 1 else None,
                    min_credibility=min_credibility if min_credibility > 1 else None,
                    only_knowledge_base=only_knowledge_base,
                    exclude_knowledge_base=exclude_knowledge_base,
                    distance_threshold=vector_distance_threshold,
                    update_stats=update_stats,
                )
            except Exception as e2:
                self.log.error(f"hybrid_recall 降级查询也失败: {e2}")
                return []

        if update_stats and rows:
            await self.vector_store.batch_update_access_stats([r["memory_id"] for r in rows if r.get("memory_id")])

        return rows