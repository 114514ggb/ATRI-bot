from logging import Logger
from typing import Dict, List, Optional

from asyncpg import Record

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.memory.memory_consolidator import MemoryConsolidator
from atribot.LLMchat.memory.memory_extractor import MemoryExtractor
from atribot.LLMchat.memory.memory_retriever import MemoryRetriever
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.RAG.rag import RAGManager
from atribot.LLMchat.RAG.vector_store import MemoryCategory


class MemorySystem:
    """记忆系统门面类"""

    def __init__(self, config: atriConfig, api_supplier: LLMConnectionManager, time_trigger: TimeTriggerSupervisor):
        self.logger: Logger = container.get("log")
        self.api_supplier: LLMConnectionManager = api_supplier
        self.config = config
        self.model = self.config.model.memory.summarize_model.model_name
        self.supplier: universal_ai_api = (
            self.api_supplier.get_filtration_connection(
                supplier_name=self.config.model.memory.summarize_model.supplier,
                model_name=self.model,
            )[0]
        ).connection_object

        self.rag = RAGManager()
        self.vector_store = self.rag.vector_store

        self.retriever = MemoryRetriever(self.rag)
        """记忆检索器"""
        self.extractor = MemoryExtractor(
            supplier = self.supplier, 
            model_name = self.model, 
            rag = self.rag, 
            retriever = self.retriever,
            request_concurrency_limit = 4
        )
        """记忆提取与总结器"""
        self.consolidator = MemoryConsolidator(
            rag=self.rag,
            retriever=self.retriever,
            time_trigger=time_trigger,
            extractor=self.extractor,
        )
        """记忆整理"""

    async def extract_stored_message(self, messages: List[Dict[str, str]], user_id: int | str) -> None:
        """提取并存储私聊记忆"""
        await self.extractor.extract_stored_message(messages, user_id)

    async def extract_stored_group_message(self, messages_str: str, bot_id: int | str, group_id: int | str) -> None:
        """提取并存储群聊记忆（基础版本）"""
        await self.extractor.extract_stored_group_message(messages_str, bot_id, group_id)

    async def extract_stored_group_message_advanced(self, messages_str: str, bot_id: int | str, group_id: int | str) -> None:
        """提取并存储群聊记忆（带召回过滤与更新合并）"""
        await self.extractor.extract_stored_group_message_advanced(messages_str, bot_id, group_id)

    async def extract_and_summarize_facts(self, message: str) -> List[str | None]:
        """从输入文本提取结构化事实列表"""
        return await self.extractor.extract_and_summarize_facts(message)

    async def extract_and_summarize_group_facts(self, message: str, bot_id: int | str) -> Dict:
        """从群聊文本提取结构化个人记忆与群话题"""
        return await self.extractor.extract_and_summarize_group_facts(message, bot_id)

    async def summarize_context(self, context: str) -> str:
        """对上下文进行压缩总结"""
        return await self.extractor.summarize_context(context)

    async def request_return_json_content(self, message: str, play_role: str) -> Dict:
        """以 JSON 形式请求并返回模型输出"""
        return await self.extractor.request_return_json_content(message, play_role)

    async def query_recently_memory(self, text: str, limit: int = 5) -> list[Record]:
        """按语义相似度查询近期记忆"""
        return await self.retriever.query_recently_memory(text, limit)

    async def query_user_recently_memory(self, user_id: int, text: str, limit: int = 5) -> list[Record]:
        """按语义相似度查询指定用户的近期记忆"""
        return await self.retriever.query_user_recently_memory(user_id, text, limit)

    async def query_memories(
        self,
        query_text: str = None,
        limit: int = 5,
        group_id: int | str = None,
        user_id: int | str = None,
        start_time: int | str = None,
        end_time: int | str = None,
        exclude_knowledge_base: bool = False,
        only_knowledge_base: bool = False,
        distance_threshold: float = 0.5,
        *,
        category: Optional[MemoryCategory] = None,
        min_importance: Optional[int] = None,
        min_credibility: Optional[int] = None,
        update_stats: bool = False,
    ) -> list[Record]:
        """通用记忆查询接口，支持多维过滤条件"""
        return await self.retriever.query_memories(
            query_text=query_text,
            limit=limit,
            group_id=group_id,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            exclude_knowledge_base=exclude_knowledge_base,
            only_knowledge_base=only_knowledge_base,
            distance_threshold=distance_threshold,
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
        """混合召回接口，融合向量检索与全文检索评分"""
        return await self.retriever.hybrid_recall(
            query_text=query_text,
            limit=limit,
            user_id=user_id,
            group_id=group_id,
            start_time=start_time,
            end_time=end_time,
            category=category,
            min_importance=min_importance,
            min_credibility=min_credibility,
            only_knowledge_base=only_knowledge_base,
            exclude_knowledge_base=exclude_knowledge_base,
            vector_distance_threshold=vector_distance_threshold,
            vector_candidates=vector_candidates,
            fulltext_candidates=fulltext_candidates,
            rrf_k=rrf_k,
            vector_weight=vector_weight,
            fulltext_weight=fulltext_weight,
            importance_weight=importance_weight,
            access_weight=access_weight,
            time_decay_weight=time_decay_weight,
            update_stats=update_stats,
        )

    async def cleanup_expired_memories(self) -> None:
        """清理过期且低价值的记忆"""
        await self.consolidator.cleanup_expired_memories()

    async def consolidate_memories(
        self,
        threshold: float = 0.90,
        recent_days: int = 7,
        use_llm_merge: bool = False,
        min_cluster_size: int = 2,
    ) -> None:
        """执行记忆整理与合并任务"""
        await self.consolidator.consolidate_memories(
            threshold=threshold,
            recent_days=recent_days,
            use_llm_merge=use_llm_merge,
            min_cluster_size=min_cluster_size,
        )
