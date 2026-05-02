import asyncio
import json
import time
from datetime import datetime
from logging import Logger
from typing import Dict, List

from atribot.common_utils import extract_json_from_text
from atribot.core.service_container import container
from atribot.core.type.context_types import Context
from atribot.LLMchat.memory.memory_retriever import MemoryRetriever
from atribot.LLMchat.memory.prompts import (
    FACT_RETRIEVAL_PROMPT,
    GROUP_MEMORY_DECISION_PROMPT,
    MEMORY_CONSOLIDATION_PROMPT,
    PURE_GROUP_FACT_RETRIEVAL_PROMPT,
    SUMMARIZE_CONTEXT_SYSTEM_PROMPT,
)
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.RAG.rag import RAGManager


class MemoryExtractor:
    """记忆提取与总结器:对对话文本进行提炼、结构化和记忆归并决策"""

    def __init__(
        self,
        supplier: universal_ai_api,
        model_name: str,
        rag: RAGManager,
        retriever: MemoryRetriever,
        request_concurrency_limit: int = 4,
    ):
        self.logger: Logger = container.get("log")
        self.supplier = supplier
        self.model = model_name
        self.rag = rag
        self.vector_store = rag.vector_store
        self.retriever = retriever
        self.request_semaphore = asyncio.Semaphore(request_concurrency_limit)
        
        
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
                    event_text:str = item.get("event","")
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

    async def extract_stored_group_message_advanced(self, messages_str:str, bot_id:int|str, group_id:int|str)->None:
        """对于群聊,从提取总结到存入向量数据库全流程(高级版本：带有回忆过滤和更新合并机制)
        但是并发可能会带来一些问题,后面是记忆是改动是批量插入的，查找的记忆中不包含并发中的改动，可能会相互依赖导致更新成问题？
        虽然但是，这个应该是最快的了，批量加并发了

        Args:
            messages_str (str): 上下文消息,的字符串
            group_id (int | str): 群号
            bot_id (int|str): 总结排除在外的bot的qq号
        """
        result:Dict = await self.extract_and_summarize_group_facts(messages_str, bot_id)
        
        self.logger.info(f"群消息总结信息:{result}")
        if not result:
            return

        items_to_evaluate = []
        
        memories: List[Dict] = result.get("memories", [])
        for user_memory_dict in memories:
            for uid_str, fact_list in user_memory_dict.items():
                for item in fact_list:
                    item:dict
                    event_text = item.get("event","")
                    if len(event_text) <= 2:
                        continue
                    try:
                        timestamp = int(datetime.strptime(item.get("occurrence_time", ""), "%Y-%m-%d %H:%M:%S").timestamp())
                    except (ValueError, TypeError):
                        timestamp = int(datetime.now().timestamp())
                        
                    items_to_evaluate.append({
                        "user_id": int(uid_str),
                        "group_id": int(group_id),
                        "timestamp": timestamp,
                        "event": event_text,
                        "category": item.get("category", "fact"),
                        "importance": int(item.get("importance", 5)),
                        "credibility": int(item.get("credibility", 5)),
                        "occurrence_time": item.get("occurrence_time") or datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    })

        group_topic: Dict = result.get("group_topic", {})
        if group_topic and group_topic.get("event"):
            topic_text = group_topic["event"]
            if len(topic_text) > 2:
                try:
                    timestamp = int(datetime.strptime(group_topic.get("occurrence_time"), "%Y-%m-%d %H:%M:%S").timestamp())
                except (ValueError, TypeError):
                    timestamp = int(datetime.now().timestamp())
                items_to_evaluate.append({
                    "user_id": None,
                    "group_id": int(group_id),
                    "timestamp": timestamp,
                    "event": topic_text,
                    "category": "group_topic",
                    "importance": int(group_topic.get("importance", 5)),
                    "credibility": int(group_topic.get("credibility", 5)),
                    "occurrence_time": group_topic.get("occurrence_time") or datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                })

        if not items_to_evaluate:
            return

        semaphore = asyncio.Semaphore(2)

        async def evaluate_item_with_semaphore(item):
            async with semaphore:
                
                candidates = []
                
                if item["category"] == "group_topic":
                    category = "group_topic"
                    group_id = item["group_id"]
                    user_id = None
                else:
                    category = None
                    group_id = None
                    user_id = item["user_id"]
                
                for r in await self.retriever.hybrid_recall(
                    query_text=item["event"],
                    limit=5,
                    group_id=group_id,
                    user_id=user_id,
                    category=category
                ):
                    candidates.append({
                        "memory_id": r["memory_id"],
                        "event": r["event"],
                        "occurrence_time": datetime.fromtimestamp(r["event_time"]).strftime("%Y-%m-%d %H:%M:%S"),
                        "category": r["category"],
                        "importance": r["importance"],
                        "credibility": r["credibility"]
                    })
                
                if not candidates:
                    return {
                        "action": "add",
                        "original_item": item,
                        "target_memory_id": None,
                        "memory": {
                            "event": item["event"],
                            "occurrence_time": item["occurrence_time"],
                            "category": item["category"],
                            "importance": item["importance"],
                            "credibility": item["credibility"]
                        }
                    }
                
                prompt_input = {
                    "new_memory": {
                        "event": item["event"],
                        "occurrence_time": item["occurrence_time"],
                        "category": item["category"],
                        "importance": item["importance"],
                        "credibility": item["credibility"]
                    },
                    "candidates": candidates
                }
                
                decision = await self.request_return_json_content(
                    message=prompt_input,
                    play_role=GROUP_MEMORY_DECISION_PROMPT
                )
                
                self.logger.info(f"群消息总结,后决策json:{decision}")
                
                action = decision.get("action", "add")
                if action not in ["add", "update", "overwrite", "skip"]:
                    action = "add"
                    
                return {
                    "action": action,
                    "original_item": item,
                    "target_memory_id": decision.get("target_memory_id"),
                    "memory": decision.get("memory", {})
                }

        evaluations = await asyncio.gather(*(evaluate_item_with_semaphore(item) for item in items_to_evaluate))

        text_to_embed = []
        for ev in evaluations:
            if ev["action"] in ["add", "update", "overwrite"]:
                memory_dict:dict = ev.get("memory") or {}
                if event_text := memory_dict.get("event", ev["original_item"]["event"]):
                    text_to_embed.append(event_text)

        if not text_to_embed:
            return

        emb_iter = iter(await self.rag.calculate_embedding(text_to_embed))

        add_args_list = []
        update_args_list = []

        for ev in evaluations:
            action = ev["action"]
            if action == "skip":
                continue
                
            orig = ev["original_item"]
            memory_dict = ev.get("memory") or {}
            event_text = memory_dict.get("event", orig["event"])
            if not event_text:
                continue
                
            emb = next(emb_iter)
            
            try:
                occurrence_time_str = memory_dict.get("occurrence_time") or orig["occurrence_time"]
                timestamp = int(datetime.strptime(occurrence_time_str, "%Y-%m-%d %H:%M:%S").timestamp())
            except (Exception):
                timestamp = orig["timestamp"]
                
            category = memory_dict.get("category", orig["category"])
            importance = int(memory_dict.get("importance", orig["importance"]))
            credibility = int(memory_dict.get("credibility", orig["credibility"]))
            
            if action == "add":
                add_args_list.append((
                    orig["user_id"],
                    orig["group_id"],
                    timestamp,
                    event_text,
                    str(emb),
                    category,
                    importance,
                    credibility
                ))
            elif action in ["update", "overwrite"]:
                target_memory_id = ev.get("target_memory_id")
                if target_memory_id is not None:
                    update_args_list.append((
                        target_memory_id,
                        timestamp,
                        event_text,
                        str(emb),
                        category,
                        importance,
                        credibility
                    ))
                else:
                    add_args_list.append((
                        orig["user_id"],
                        orig["group_id"],
                        timestamp,
                        event_text,
                        str(emb),
                        category,
                        importance,
                        credibility
                    ))

        #这里目前有个冲突问题，同一批item可能决策出对同一条旧记忆进行操作，然后后执行的会留下结果前面的被覆盖，应该不是什么问题

        if add_args_list:
            await self.vector_store.batch_add_memories(add_args_list)
        if update_args_list:
            await self.vector_store.batch_update_memories(update_args_list)
                     
        
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
        if return_json := await self.request_return_json_content(message, PURE_GROUP_FACT_RETRIEVAL_PROMPT+f"\n请详细记录bot账号<user_id>{bot_id}</user_id>相关的,但是不要记录bot的"):
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

    async def merge_cluster_event_with_llm(self, category: str, cluster_rows: List[dict]) -> str | None:
        """交给llm来合并相似的语句"""

        payload = {
            "category": category,
            "memories": [
                {
                    "memory_id": row["memory_id"],
                    "event": row["event"],
                    "event_time": datetime.fromtimestamp(row["event_time"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "importance": row["importance"],
                    "credibility": row["credibility"],
                }
                for row in cluster_rows
            ],
        }
        result = await self.request_return_json_content(
            message=payload,
            play_role=MEMORY_CONSOLIDATION_PROMPT,
        )
        merged_event = result.get("merged_event") if isinstance(result, dict) else None
        if isinstance(merged_event, str) and len(merged_event.strip()) > 2:
            return merged_event.strip()
        return None

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
                async with self.request_semaphore:
                    assistant_content:str = (
                        await self.supplier.generate_json_ample(self.model, parameters)
                    )['choices'][0]['message'].get('content')
            except Exception as e:
                self.logger.error(f"第{i}次总结请求出错:{e}")
                await asyncio.sleep(1)

            if assistant_content:
                try:
                    return json.loads(assistant_content)
                except json.JSONDecodeError:
                    extracted = extract_json_from_text(assistant_content)
                    if isinstance(extracted, dict):
                        return extracted
                    self.logger.error(f"总结的提取解析json问题,data:{assistant_content}")
                    
                except Exception:
                    self.logger.error(f"总结的提取解析json问题,data:{assistant_content}")

            await asyncio.sleep(1)

        return {}