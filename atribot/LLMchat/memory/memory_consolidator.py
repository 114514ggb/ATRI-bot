import asyncio
import time
from logging import Logger
from typing import Dict, List, Optional, Tuple

from atribot.common_utils import ClusterUtils
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.memory.memory_extractor import MemoryExtractor
from atribot.LLMchat.memory.memory_retriever import MemoryRetriever
from atribot.LLMchat.RAG.rag import RAGManager


class MemoryConsolidator:
    """
    记忆整理优化器类
    专门负责处理冗余记忆、向量聚类和利用大模型合并等耗时后台操作
    """
    
    def __init__(
        self,
        rag: RAGManager,
        retriever: MemoryRetriever,
        time_trigger: TimeTriggerSupervisor,
        extractor: Optional[MemoryExtractor] = None,
    ):
        self.logger: Logger = container.get("log")
        self.time_trigger: TimeTriggerSupervisor = time_trigger
        self.rag = rag
        self.vector_store = rag.vector_store
        self.retriever = retriever
        self.extractor = extractor
        self.time_trigger.add_task(
            task_id=1101,
            func=self.scheduled_memory_maintenance,
            trigger_delta=86400,
            interval=86400,
            timeout=600.0,
            remarks="记忆系统24小时维护",
        )

    async def scheduled_memory_maintenance(self) -> None:
        """统一触发记忆维护"""
        self.logger.info("开始执行定时记忆维护任务")
        await self.cleanup_expired_memories()
        await self.consolidate_memories_sequential(use_llm_merge=True)
        self.logger.info("定时记忆维护任务执行完成")


    async def cleanup_expired_memories(self):
        """简单清理太久前记忆,只是简单条件删除过久的没什么意义的记忆"""
        sql = """
            DELETE FROM atri_memory
            WHERE memory_id IN (
                SELECT memory_id FROM atri_memory
                WHERE (
                    (last_accessed < EXTRACT(EPOCH FROM NOW() - INTERVAL '90 days')::bigint
                    OR last_accessed IS NULL)
                    AND importance < 5
                    AND created_at < EXTRACT(EPOCH FROM NOW() - INTERVAL '90 days')::bigint
                )
                OR (
                    category = 'group_topic'
                    AND event_time < EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')::bigint
                )
            )
        """
        async with self.vector_store.vector_database as db:
            await db.execute_with_pool(
                query = sql
            )

    async def consolidate_memories(
        self,
        threshold: float = 0.1,
        recent_days: int = 7,
        use_llm_merge: bool = False,
        min_cluster_size: int = 2,
    ) -> None:
        """按组对近期记忆做语义相似整理与去重。

        仅整理 `user_id` 非空的记忆，按 `(user_id, category)` 分组。在每个分组内，先基于向量相似度
        构建聚类，再对每个簇保留一条主记忆并删除冗余记忆；必要时可通过 LLM 合并文本
        同时回写更高的质量分数

        Args:
            threshold: 最高的余弦距离阈值，取值范围为 [0, 2]
            recent_days: 候选记忆的时间窗口（天）
            use_llm_merge: 是否使用 LLM 将同簇记忆合并为一条文本
            min_cluster_size: 分组/簇参与整理所需的最小记忆条数
        """
        self.logger.info(
            f"开始执行记忆整理任务... threshold={threshold}, recent_days={recent_days}, use_llm_merge={use_llm_merge}, min_cluster_size={min_cluster_size}"
        )

        if min_cluster_size < 2:
            min_cluster_size = 2

        start_time = int(time.time()) - max(recent_days, 1) * 86400

        sql = """
            WITH candidates AS (
                SELECT
                    memory_id,
                    user_id,
                    event_time,
                    event,
                    category,
                    importance,
                    credibility,
                    created_at
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
                HAVING COUNT(*) >= $2
            )
            SELECT
                c.memory_id,
                c.user_id,
                c.event_time,
                c.event,
                c.category,
                c.importance,
                c.credibility,
                c.created_at
            FROM candidates c
            JOIN valid_groups g
                ON c.user_id IS NOT DISTINCT FROM g.user_id
               AND c.category = g.category
            ORDER BY c.user_id NULLS FIRST, c.category, c.created_at DESC
        """

        async with self.vector_store.vector_database as db:
            rows = await db.execute_with_pool(sql, (start_time, min_cluster_size), fetch_type="all")

        if not rows:
            self.logger.info("记忆整理结束：没有满足条件的数据")
            return

        groups: Dict[Tuple[int, str], List[dict]] = {}
        for row in rows:
            key = (row["user_id"], row["category"])
            groups.setdefault(key, []).append(row)

        total_clusters = 0
        deleted_count = 0
        updated_count = 0
        grouped_edges = await self.retriever.query_similarity_edges_grouped(
            start_time, threshold, min_cluster_size
        )

        semaphore = asyncio.Semaphore(2)
        
        for (user_id, category), group_rows in groups.items():
            if len(group_rows) < min_cluster_size:
                continue

            memory_id_to_row = {row["memory_id"]: row for row in group_rows}
            memory_ids = list(memory_id_to_row.keys())
            if len(memory_ids) < min_cluster_size:
                continue

            edges = grouped_edges.get((user_id, category), [])
            clusters = ClusterUtils.build_clusters(memory_ids, edges)

            for cluster_ids in clusters:
                if len(cluster_ids) < min_cluster_size:
                    continue

                total_clusters += 1
                cluster_rows = [memory_id_to_row[memory_id] for memory_id in cluster_ids]
                cluster_rows.sort(
                    key=lambda x: (
                        x.get("importance", 0),
                        x.get("credibility", 0),
                        x.get("event_time", 0),
                        x.get("created_at", 0),
                    ),
                    reverse=True,
                )

                keeper = cluster_rows[0]
                redundant_ids = [r["memory_id"] for r in cluster_rows[1:]]

                merged_event = None
                if use_llm_merge and len(cluster_rows) > 1:
                    try:
                        async with semaphore:
                            merged_event = await self.extractor.merge_cluster_event_with_llm(category, cluster_rows)
                    except Exception as e:
                        self.logger.error(f"LLM合并失败,回退保留原文本: {e}")

                final_event = (merged_event or keeper["event"] or "").strip()
                if not final_event:
                    final_event = keeper["event"]

                final_importance = max(r.get("importance", 5) for r in cluster_rows)
                final_credibility = max(r.get("credibility", 5) for r in cluster_rows)
                final_event_time = max(r.get("event_time", 0) for r in cluster_rows)

                if redundant_ids:
                    deleted_num = await self.vector_store.batch_delete_memories(redundant_ids)
                    deleted_count += deleted_num

                if (
                    final_event == keeper["event"]
                    or final_importance == keeper["importance"]
                    or final_credibility == keeper["credibility"]
                    or final_event_time == keeper["event_time"]
                ):
                    continue

                try:
                    embedding = (await self.rag.calculate_embedding([final_event]))[0]
                except Exception as e:
                    self.logger.error(f"记忆重算 embedding 失败, memory_id={keeper['memory_id']}, error={e}")
                    continue

                try:
                    updated = await self.vector_store.update_memory(
                        keeper["memory_id"],
                        event_time=final_event_time,
                        event=final_event,
                        event_vector=embedding,
                        category=keeper["category"],
                        importance=final_importance,
                        credibility=final_credibility,
                    )
                    if updated:
                        updated_count += 1
                except Exception as e:
                    self.logger.error(f"更新保留记忆失败, memory_id={keeper['memory_id']}, error={e}")

        self.logger.info(
            f"记忆整理完成: groups={len(groups)}, consolidated_clusters={total_clusters}, deleted={deleted_count}, updated={updated_count}"
        )

    async def consolidate_memories_sequential(
        self,
        threshold: float = 0.1,
        recent_days: int = 7,
        use_llm_merge: bool = False,
        min_cluster_size: int = 2,
    ) -> None:
        """按组对近期记忆做语义相似整理与去重（非并发、非批量版本）

        一条一条处理记忆簇，合并或修改完成后直接存入数据库并在之后再进行其余记忆的操作
        
        Args:
            threshold: 最高的余弦距离阈值，取值范围为 [0, 2]
            recent_days: 候选记忆的时间窗口（天）
            use_llm_merge: 是否使用 LLM 将同簇记忆合并为一条文本
            min_cluster_size: 分组/簇参与整理所需的最小记忆条数
        """
        self.logger.info(
            f"开始执行顺序记忆整理任务... threshold={threshold}, recent_days={recent_days}, use_llm_merge={use_llm_merge}, min_cluster_size={min_cluster_size}"
        )

        if min_cluster_size < 2:
            min_cluster_size = 2

        start_time = int(time.time()) - max(recent_days, 1) * 86400

        sql = """
            WITH candidates AS (
                SELECT
                    memory_id,
                    user_id,
                    event_time,
                    event,
                    category,
                    importance,
                    credibility,
                    created_at
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
                HAVING COUNT(*) >= $2
            )
            SELECT
                c.memory_id,
                c.user_id,
                c.event_time,
                c.event,
                c.category,
                c.importance,
                c.credibility,
                c.created_at
            FROM candidates c
            JOIN valid_groups g
                ON c.user_id IS NOT DISTINCT FROM g.user_id
               AND c.category = g.category
            ORDER BY c.user_id NULLS FIRST, c.category, c.created_at DESC
        """

        async with self.vector_store.vector_database as db:
            rows = await db.execute_with_pool(sql, (start_time, min_cluster_size), fetch_type="all")

        if not rows:
            self.logger.info("顺序记忆整理结束：没有满足条件的数据")
            return

        groups: Dict[Tuple[int, str], List[dict]] = {}
        for row in rows:
            key = (row["user_id"], row["category"])
            groups.setdefault(key, []).append(row)

        total_clusters = 0
        deleted_count = 0
        updated_count = 0
        
        # 为了保证绝对的顺序性，获取连通图以聚类
        grouped_edges = await self.retriever.query_similarity_edges_grouped(
            start_time, threshold, min_cluster_size
        )

        for (user_id, category), group_rows in groups.items():
            if len(group_rows) < min_cluster_size:
                continue

            memory_id_to_row = {row["memory_id"]: row for row in group_rows}
            memory_ids = list(memory_id_to_row.keys())
            if len(memory_ids) < min_cluster_size:
                continue

            edges = grouped_edges.get((user_id, category), [])
            clusters = ClusterUtils.build_clusters(memory_ids, edges)

            for cluster_ids in clusters:
                if len(cluster_ids) < min_cluster_size:
                    continue

                total_clusters += 1
                cluster_rows = [memory_id_to_row[memory_id] for memory_id in cluster_ids]
                cluster_rows.sort(
                    key=lambda x: (
                        x.get("importance", 0),
                        x.get("credibility", 0),
                        x.get("event_time", 0),
                        x.get("created_at", 0),
                    ),
                    reverse=True,
                )

                keeper = cluster_rows[0]
                redundant_ids = [r["memory_id"] for r in cluster_rows[1:]]

                merged_event = None
                if use_llm_merge and len(cluster_rows) > 1:
                    try:
                        # 不使用 semaphore，直接顺序执行
                        merged_event = await self.extractor.merge_cluster_event_with_llm(category, cluster_rows)
                    except Exception as e:
                        self.logger.error(f"LLM合并失败,回退保留原文本: {e}")

                final_event = (merged_event or keeper["event"] or "").strip()
                if not final_event:
                    final_event = keeper["event"]

                final_importance = max(r.get("importance", 5) for r in cluster_rows)
                final_credibility = max(r.get("credibility", 5) for r in cluster_rows)
                final_event_time = max(r.get("event_time", 0) for r in cluster_rows)

                if redundant_ids:
                    deleted_num = await self.vector_store.batch_delete_memories(redundant_ids)
                    deleted_count += deleted_num

                if (
                    final_event == keeper["event"]
                    and final_importance == keeper["importance"]
                    and final_credibility == keeper["credibility"]
                    and final_event_time == keeper["event_time"]
                ):
                    continue

                try:
                    embedding = (await self.rag.calculate_embedding([final_event]))[0]
                except Exception as e:
                    self.logger.error(f"记忆重算 embedding 失败, memory_id={keeper['memory_id']}, error={e}")
                    continue

                try:
                    updated = await self.vector_store.update_memory(
                        keeper["memory_id"],
                        event_time=final_event_time,
                        event=final_event,
                        event_vector=embedding,
                        category=keeper["category"],
                        importance=final_importance,
                        credibility=final_credibility,
                    )
                    if updated:
                        updated_count += 1
                except Exception as e:
                    self.logger.error(f"更新保留记忆失败, memory_id={keeper['memory_id']}, error={e}")

        self.logger.info(
            f"顺序记忆整理完成: groups={len(groups)}, consolidated_clusters={total_clusters}, deleted={deleted_count}, updated={updated_count}"
        )
