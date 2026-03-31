import asyncio
import json
import re
import time
from datetime import datetime
from logging import Logger
from typing import Any, Dict, List, Optional

from asyncpg import Record

from atribot.core.service_container import container
from atribot.core.type.context_types import Context
from atribot.LLMchat.memory.prompts import (
    FACT_RETRIEVAL_PROMPT,
    PURE_GROUP_FACT_RETRIEVAL_PROMPT,
    SUMMARIZE_CONTEXT_SYSTEM_PROMPT,
)
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.RAG.rag import RAGManager
from atribot.LLMchat.RAG.vector_store import MemoryCategory


class memorySystem:
    """管理记忆类"""
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.api_supplier:LLMConnectionManager = container.get("LLMSupplier")
        self.config = container.get("config")
        self.model = self.config.model.memory.summarize_model.model_name
        self.supplier:universal_ai_api = (self.api_supplier.get_filtration_connection(
                supplier_name = self.config.model.memory.summarize_model.supplier,
                model_name = self.model
            )[0]).connection_object
        self.rag = RAGManager()
        self.vector_store = self.rag.vector_store
        
    async def extract_stored_message(self, messages:List[Dict[str,str]], user_id:int|str)->None:
        """对个人聊天,从提取到存入向量数据库全流程

        Args:
            messages (List[Dict[str,str]]): 上下文消息
            user_id (int | str): 用户ID
        """
        if summarize_list :=  await self.extract_and_summarize_facts(str(messages)):
            
            event_time = int(time.time())
            await self.vector_store.batch_add_memories([
                (user_id, 0, event_time, text, emb, "fact", 5, 5)
                for text, emb in zip(summarize_list, await self.rag.calculate_embedding(summarize_list))
            ])


    async def extract_stored_group_message(self, messages_str:str, bot_id:int|str, group_id:int|str)->None:
        """对于群聊,从提取总结到存入向量数据库全流程

        Args:
            messages_str (str): 上下文消息,的字符串
            group_id (int | str): 群号
            bot_id (int|str): 总结排除在外的bot的qq号
        """
        result:Dict = await self.extract_and_summarize_group_facts(messages_str, bot_id)
        
        self.logger.info(f"群消息总结信息:{result}")
        
        args_list = []
        
        memories: List[Dict] = result.get("memories", [])
        for user_memory_dict in memories:
            for uid_str, fact_list in user_memory_dict.items():
                for item, emb in zip(fact_list, await self.rag.calculate_embedding([item["event"] for item in fact_list])):
                    event_text = item.get("event","")
                    if len(event_text) <= 2:
                        continue
                    try:
                        timestamp = int(datetime.strptime(item.get("occurrence_time", ""), "%Y-%m-%d %H:%M:%S").timestamp())
                    except (ValueError, TypeError):
                        timestamp = int(datetime.now().timestamp())
                    args_list.append((
                        int(uid_str),
                        group_id,
                        timestamp,
                        event_text,
                        str(emb),
                        item.get("category", "fact"),
                        int(item.get("importance", 5)),
                        int(item.get("credibility", 5)),
                    ))

        group_topic: Dict = result.get("group_topic", {})
        if group_topic and group_topic.get("event"):
            topic_text = group_topic["event"]
            if len(topic_text) > 2:
                try:
                    timestamp = int(datetime.strptime(group_topic.get("occurrence_time"), "%Y-%m-%d %H:%M:%S").timestamp())
                except (ValueError, TypeError):
                    timestamp = int(datetime.now().timestamp())
                if topic_embeddings := await self.rag.calculate_embedding(topic_text):
                    args_list.append((
                        None,
                        group_id,
                        timestamp,
                        topic_text,
                        str(topic_embeddings[0]),
                        "group_topic",
                        int(group_topic.get("importance", 5)),
                        int(group_topic.get("credibility", 5)),
                    ))

        if args_list:
            await self.vector_store.batch_add_memories(args_list)
                     
        
    async def extract_and_summarize_facts(self, message:str)->List[str|None]:
        """从用户输入文本中提取关键信息,并总结成一个结构化的事实.可以输入多条,但是不适用于多人聊天环境

        Args:
            message (str): 输入文本

        Returns:
            list[str]: 可能为空的总结str
        """
        if return_json := await self.request_return_json_content(message, FACT_RETRIEVAL_PROMPT):
            return return_json.get("facts",[])
        else:
            return []
        
    async def extract_and_summarize_group_facts(self, message:str, bot_id:int|str)->Dict:
        """从群聊文本中提取关键信息,并总结成一个结构化的事实

        Args:
            message (str): 输入文本
            bot_id (int): 自己的id

        Returns:
            Dict: 可能为空的总结,格式为:
            {
              "memories": [
                {
                  "用户标识user_id": [
                    {
                      "event": "记忆内容",
                      "occurrence_time": "2026-03-09 01:29:38",
                      "category": "preference|fact|experience|emotion",
                      "importance": 1-10,
                      "credibility": 1-10
                    }
                  ]
                }
              ],
              "group_topic": {
                "event": "群话题描述",
                "occurrence_time": "2026-03-09 01:29:38",
                "importance": 1-10,
                "credibility": 1-10
              }
            }
        """
        if return_json := await self.request_return_json_content(message, PURE_GROUP_FACT_RETRIEVAL_PROMPT+f"详细记录bot账号<user_id>{bot_id}</user_id>相关的,但是不要记录bot的"):
            return return_json
        else:
            return {}
        
    async def summarize_context(self, context:str)->str:
        """对一段文本进行关键性总结,为模型进行上下文压缩

        Args:
            context (str): 要进行总结的文本

        Returns:
            str: 总结后的文本
        """
        if return_json := await self.request_return_json_content(
            message = context, 
            play_role = SUMMARIZE_CONTEXT_SYSTEM_PROMPT
        ):
            return return_json.get("summarize","")
        else:
            return ""
        
        
    async def request_return_json_content(self, message:str, play_role:str)->Dict:
        """发起请求获取json

        Args:
            message (str): Input
            play_role (str): 人物提示词

        Returns:
            Dict: 可能为空的模型返回
        """
        private_context = Context(play_role = play_role)
        private_context.add_user_message(
            f"Input:\n{message}"
        )
        
        parameters = {
            "messages":private_context.get_messages(),
            "temperature":0,
            # "max_tokens": 65536,
            # "reasoning_effort": "high",
            "response_format":{ "type": "json_object" },
            "stream":False
        }
        
        assistant_content = None
        
        for i in range(5):
            try:
                assistant_content:str = (await self.supplier.generate_json_ample(self.model, parameters))['choices'][0]['message'].get('content')
            except Exception as e:
                self.logger.error(f"第{i}次总结请求出错:{e}")
                await asyncio.sleep(1)
                
            if assistant_content:
                try:
                    return json.loads(assistant_content)
                except json.JSONDecodeError: 
                    extracted_str:str = None #兼容一些奇怪的情况
            
                    if match := re.search(r"```(?:json)?\s*(\{.*?\})\s*```", assistant_content, re.DOTALL):
                        extracted_str = match.group(1)
                    
                    elif match := re.search(r"\{.*\}", assistant_content, re.DOTALL):
                        extracted_str = match.group(0)
                    
                    if extracted_str:
                        try:
                            return json.loads(extracted_str)
                        except json.JSONDecodeError:
                            self.logger.error(f"总结的提取解析json问题,data:{assistant_content}")
                    
                except Exception:
                    self.logger.error(f"总结的提取解析json问题,data:{assistant_content}")

            await asyncio.sleep(1)

        return {}
    
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
                    params = (str(embeddin_list[0]), limit),
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
                    params = (str(embeddin_list[0]), user_id, limit),
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
            (await self.rag.calculate_embedding(query_text))[0] if query_text else None,
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
        FULL OUTER JOIN 合并 → 叠加 importance/access_count/时间衰减 附加分 → 排序截断,

        SQL 结构(CTE 链):
            vec_ranked   — 向量路按距离升序,取 vector_candidates 候选,附带行号
            ft_ranked    — 全文路按 pgroonga_score 降序,取 fulltext_candidates 候选,附带行号
            merged       — FULL OUTER JOIN,COALESCE 取非 NULL 的基础字段
            scored       — 计算 hybrid_score:
                             $vector_weight  / (rrf_k + vec_rank)   向量 RRF 贡献,无命中则 0
                           + $fulltext_weight / (rrf_k + ft_rank)    全文 RRF 贡献,无命中则 0
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

        embedding_list = await self.rag.calculate_embedding(query_text)
        if not embedding_list:
            return []
        query_vector = embedding_list[0]

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
            self.logger.error(f"hybrid_recall 混合查询失败,降级到纯向量: {e}")
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
                self.logger.error(f"hybrid_recall 降级查询也失败: {e2}")
                return []

        if update_stats and rows:
            await self.vector_store.batch_update_access_stats([r["memory_id"] for r in rows if r.get("memory_id")])

        return rows