from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.memory.prompts import FACT_RETRIEVAL_PROMPT,GROUP_FACT_RETRIEVAL_PROMPT
from atribot.core.service_container import container
from atribot.LLMchat.RAG.RAG import RAGManager
from atribot.core.types import Context
from datetime import datetime
from typing import List,Dict,Any
from logging import Logger
import json
import time




class memirySystem:
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.api_supplier:ai_connection_manager = container.get("LLMSupplier")
        self.config = container.get("config")
        self.model = self.config.model.memiry.summarize_model.model_name
        self.supplier:universal_ai_api = (self.api_supplier.get_filtration_connection(
                supplier_name = self.config.model.memiry.summarize_model.supplier,
                model_name = self.model
            )[0]).connection_object
        self.rag = RAGManager()
        self.vector_store = self.rag.vector_store
        
    async def extract_stored_message(self, messages:List[Dict[str:str]], user_id:int|str)->None:
        """对个人聊天，从提取到存入向量数据库全流程

        Args:
            messages (List[Dict[str:str]]): 上下文消息
            user_id (int | str): 用户ID
        """
        summarize_list = await self.extract_and_summarize_facts(str(messages))
        if summarize_list:
            
            event_time = int(time.time())
            await self.vector_store.batch_add_memories([
                (0, user_id, event_time, text, emb)
                for text, emb in zip(summarize_list, await self.rag.calculate_embedding(summarize_list))
            ])


    async def extract_stored_group_message(self, messages:List[Dict[str:str]])->None:
        """对于群聊，从提取总结到存入向量数据库全流程

        Args:
            messages (List[Dict[str:str]]): 上下文消息
            group_id (int | str): 群号
        """
        summarize_list = await self.extract_and_summarize_group_facts(str(messages))
        
        args_list = []
        
        for summarize in summarize_list:
            user_id = summarize["qq_id"]
            for affair in summarize["affair"]:
                affair:Dict
                for time_text,facts in affair.items():
                    timestamp = int(datetime.strptime(time_text, "%Y-%m-%d %H:%M:%S").timestamp())
                    args_list += [
                        (None, user_id, timestamp, text, emb)
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
        
    async def extract_and_summarize_group_facts(self, message:str)->List[Dict[str:str|str:Dict[str:List[str]]]]:
        """从用户输入文本中提取关键信息，并总结成一个结构化的事实

        Args:
            message (str): 输入文本

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
        if return_json := await self.request_return_json_content(message, GROUP_FACT_RETRIEVAL_PROMPT):
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
        private_context = Context(Play_role = play_role)
        private_context.add_user_message(
            f"Input:\n{message}"
        )
        
        parameters = {
            "messages":private_context.get_messages(),
            "temperature":0.0,
            "max_tokens": 8192,
            "reasoning_effort": "high",
            "response_format":{ "type": "json_object" }
        }
        
        assistant_message:dict = (await self.supplier.generate_json_ample(self.model, parameters))['choices'][0]['message']
        
        if assistant_content := assistant_message.get('content'):
            return json.loads(assistant_content)
        else:
            return {}
        
    async def query_memory(self, text:str, user_id:int|str)->List[tuple[dict[str:str]]]:
        """简单根据文本向量和user_id查询数据库最相似消息

        Args:
            text (str): 要文本搜索的文本,太长会截取
            user_id (int | str): 筛选的ID

        Returns:
            List[tuple[dict[str:str]]]: 返回查询到的表行最多5条
        """
        embeddin_list = await self.rag.calculate_embedding(text[500])
        
        sql = """
        SELECT 
            event_time,
            event,
            created_at,
        FROM atri_memory
        WHERE user_id = $1
        AND event_vector <=> $2::vector(1024) <= 0.5
        ORDER BY event_vector <=> $2::vector(1024) ASC
        LIMIT 5
        """
        
        async with self.vector_store.vector_database as db:
            return await db.execute_with_pool(
                sql = sql,
                params = (user_id, embeddin_list)
            )
    
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
        
        self.vector_store.query_memories(
            await self.rag.calculate_embedding(query_text) ,
            limit,
            group_id,
            user_id,
            start_time,
            end_time,
            exclude_knowledge_base,
            only_knowledge_base,
            distance_threshold
        )