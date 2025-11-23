from atribot.LLMchat.memory.prompts import FACT_RETRIEVAL_PROMPT,PURE_GROUP_FACT_RETRIEVAL_PROMPT
from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.core.service_container import container
from atribot.LLMchat.RAG.RAG import RAGManager
from atribot.core.types import Context
from typing import List,Dict,Any
from datetime import datetime
from logging import Logger
import asyncio
import json
import time




class memorySystem:
    """管理记忆类"""
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.api_supplier:ai_connection_manager = container.get("LLMSupplier")
        self.config = container.get("config")
        self.model = self.config.model.memory.summarize_model.model_name
        self.supplier:universal_ai_api = (self.api_supplier.get_filtration_connection(
                supplier_name = self.config.model.memory.summarize_model.supplier,
                model_name = self.model
            )[0]).connection_object
        self.rag = RAGManager()
        self.vector_store = self.rag.vector_store
        
    async def extract_stored_message(self, messages:List[Dict[str,str]], user_id:int|str)->None:
        """对个人聊天，从提取到存入向量数据库全流程

        Args:
            messages (List[Dict[str,str]]): 上下文消息
            user_id (int | str): 用户ID
        """
        summarize_list = await self.extract_and_summarize_facts(str(messages))
        if summarize_list:
            
            event_time = int(time.time())
            await self.vector_store.batch_add_memories([
                (0, user_id, event_time, text, emb)
                for text, emb in zip(summarize_list, str(await self.rag.calculate_embedding(summarize_list)[0]))
            ])


    async def extract_stored_group_message(self, messages:List[Dict[str,str]], bot_id:int|str, group_id:int|str)->None:
        """对于群聊，从提取总结到存入向量数据库全流程

        Args:
            messages (List[Dict[str,str]]): 上下文消息
            group_id (int | str): 群号
            bot_id (int|str): 总结排除在外的bot的qq号
        """
        summarize_list:List[Dict[str,str]|Dict[str,Dict]] = await self.extract_and_summarize_group_facts(str(messages),bot_id)
        
        self.logger.info(f"群消息总结信息:{summarize_list}")
        
        args_list = []
        
        for summarize in summarize_list:
            user_id = summarize["qq_id"]
            for time_text,facts in summarize["affair"].items():
                timestamp = int(datetime.strptime(time_text, "%Y-%m-%d %H:%M:%S").timestamp())
                args_list += [
                    (group_id, user_id, timestamp, text, str(emb))
                    for text, emb in zip(facts, await self.rag.calculate_embedding(facts))
                ]
    
        await self.vector_store.batch_add_memories(args_list)
                     
        
    async def extract_and_summarize_facts(self, message:str)->List[str|None]:
        """从用户输入文本中提取关键信息，并总结成一个结构化的事实.可以输入多条，但是不适用于多人聊天环境

        Args:
            message (str): 输入文本

        Returns:
            list[str]: 可能为空的总结str
        """
        if return_json := await self.request_return_json_content(message, FACT_RETRIEVAL_PROMPT):
            return return_json.get("facts",[])
        else:
            return []
        
    async def extract_and_summarize_group_facts(self, message:str, bot_id:int|str)->List[Dict[str,List[Dict]]]:
        """从群聊文本中提取关键信息，并总结成一个结构化的事实

        Args:
            message (str): 输入文本
            bot_id (int): 排除自己id

        Returns:
            list[Dict]: 可能为空的总结,里面格式
            {"facts" : [
                {
                    "qq_id":2990178383,
                    "affair":{{
                        "2024-6-8 6-32-42":["Had a meeting with John at 3pm", "Discussed the new project"]
                    }
                }
            ]}
        """
        if return_json := await self.request_return_json_content(message, PURE_GROUP_FACT_RETRIEVAL_PROMPT+f"排除<qq_id>{bot_id}</qq_id>的bot发送的消息"):
            return return_json.get("facts",[])
        else:
            return []
        
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
            "temperature":0.0,
            # "max_tokens": 65536,
            # "reasoning_effort": "high",
            "response_format":{ "type": "json_object" }
        }
        
        assistant_message = {}
        
        for i in range(3):
            try:
                assistant_message:Dict[str, Any] = (await self.supplier.generate_json_ample(self.model, parameters))['choices'][0]['message']
                break
            except Exception as e:
                self.logger.error(f"第{i}次总结请求出错:{e}")
                await asyncio.sleep(1)
        
        if assistant_content := assistant_message.get('content',"").strip():
            return json.loads(assistant_content)
        else:
            return {}
    
    async def query_user_recently_memory(self, text:str, user_id:int, limit:int = 5)->List[tuple[dict[str,str]]]:
        """简单根据文本向量和user_id查询数据库最相似消息,返回余弦距离<0.5,和最近30天内的消息

        Args:
            text (str): 要文本搜索的文本,太长会截取
            user_id (int | str): 筛选的ID
            limit (int): 返回最大数量

        Returns:
            List[tuple[dict[str,str]]]: 返回查询到的表行最多5条
        """
        if embeddin_list := await self.rag.calculate_embedding(text[:500]):
        
            sql = """
            SELECT 
                event_time,
                event
            FROM atri_memory
            WHERE user_id = $1
            AND event_vector <=> $2::vector(1024) <= 0.5
            AND event_time >= EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - INTERVAL '30 days')::bigint
            ORDER BY event_vector <=> $2::vector(1024) ASC
            LIMIT $3
            """
            
            async with self.vector_store.vector_database as db:
                return await db.execute_with_pool(
                    query = sql,
                    params = (user_id, str(embeddin_list[0]), limit),
                    fetch_type = "all"
                )
        
        return []
    
    async def query_user_memory(self, text:str, user_id:int, limit:int = 5)->List[tuple[dict[str,str]]]:
        """简单根据文本向量和user_id查询数据库最相似消息,返回余弦距离<0.5

        Args:
            text (str): 要文本搜索的文本,太长会截取
            user_id (int | str): 筛选的ID
            limit (int): 返回最大数量

        Returns:
            List[tuple[dict[str,str]]]: 返回查询到的表行最多5条
        """
        if embeddin_list := await self.rag.calculate_embedding(text[:500]):
            sql = """
            SELECT 
                event_time,
                event
            FROM atri_memory
            WHERE user_id = $1
            AND event_vector <=> $2::vector(1024) <= 0.5
            ORDER BY event_vector <=> $2::vector(1024) ASC
            LIMIT $3
            """
            async with self.vector_store.vector_database as db:
                return await db.execute_with_pool(
                    query = sql,
                    params = (user_id, str(embeddin_list[0]), limit),
                    fetch_type = "all"
                )

        return []
    
    async def query_add_memory(self, text:str, limit:int = 5)->List[tuple[dict[str,str]]]:
        """查询全部记忆"""
        if embeddin_list := await self.rag.calculate_embedding(text[:500]):
        
            sql = """   
            SELECT 
                event_time,
                user_id,
                event
            FROM atri_memory
            WHERE event_vector <=> $1::vector(1024) <= 0.6
            ORDER BY event_vector <=> $1::vector(1024) ASC
            LIMIT $2
            """
            async with self.vector_store.vector_database as db:
                return await db.execute_with_pool(
                    query = sql,
                    params = (str(embeddin_list[0]),limit),
                    fetch_type = "all"
                )
        
        return []
    
    async def query_memories(
        self,
        query_text: List[float],
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
        记忆查询接口
        
        Args:
            query_text: 查询文本，会自然转换向量
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
        
        return await self.vector_store.query_memories(
            str((await self.rag.calculate_embedding(query_text))[0]) ,
            limit,
            group_id,
            user_id,
            start_time,
            end_time,
            exclude_knowledge_base,
            only_knowledge_base,
            distance_threshold
        )