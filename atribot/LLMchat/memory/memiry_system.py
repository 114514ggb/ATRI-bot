from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.memory.prompts import FACT_RETRIEVAL_PROMPT
from atribot.core.service_container import container
from atribot.LLMchat.RAG.RAG import RAGManager
from atribot.core.types import Context
from typing import List,Dict
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
        
    async def extract_stored_message(self,messages:List[Dict[str:str]], user_id:int|str)->None:
        """对个人聊天，从提取到存入向量数据库全流程

        Args:
            messages (List[Dict[str:str]]): 上下文消息
            user_id (int | str): 用户ID
        """
        summarize_list = await self.extract_and_summarize_facts(str(messages))
        if summarize_list:
            
            await self.vector_store.add_user(
                text_list = summarize_list,
                embedding_list = await self.rag.calculate_embedding(summarize_list),
                user_id = user_id,
                event_time = int(time.time()) #其实用这个时间不太准确
            )

        
    async def extract_and_summarize_facts(self, message:str)->List[str]:
        """从用户输入文本中提取关键信息，并总结成一个结构化的事实.可以输入多条，但是不适用于多人聊天环境

        Args:
            message (str): 输入文本

        Returns:
            list[str]: 可能为空的总结str
        """
        private_context = Context(Play_role = FACT_RETRIEVAL_PROMPT)
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
            return json.loads(assistant_content).get("facts",[]) 
        else:
            return []