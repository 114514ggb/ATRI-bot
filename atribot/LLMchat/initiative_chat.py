from atribot.core.cache.management_chat_example import ChatManager
from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.core.service_container import container
from atribot.core.types import RichData,TimeWindow
from atribot.core.types import Context
from typing import List,Dict
from logging import Logger
import json




class initiativeChat:
    """决定bot如何在合适的时机加入聊天"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.chat_manager:ChatManager = container.get("ChatManager")
        self.api_supplier:ai_connection_manager = container.get("LLMSupplier")
        self.config = container.get("config")
        self.model = self.config.model.memory.summarize_model.model_name
        self.supplier:universal_ai_api = (self.api_supplier.get_filtration_connection(
                supplier_name = self.config.model.memory.summarize_model.supplier,
                model_name = self.model
            )[0]).connection_object
        
    
    async def decision(self, message:RichData)->bool:
        """决策是否应该发言"""
        data = message.primeval
        group_id = data["group_id"]
        
        if self.chat_manager.get_bot_ratio_in_group(group_id) < 0.8: 
            #不能太吵,消息占比不是太高的时候才会考虑
            
            user_id:int = data["user_id"]
            group_context = self.chat_manager.get_group_context(group_id)
            decision_parameters = group_context.LLM_chat_decision_parameters
            if user_id == decision_parameters.last_trigger_user_id and decision_parameters.get_seconds_since_user()< 8:
                #考虑到追问的情况
                pass

            
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
            message
        )
        
        parameters = {
            "messages":private_context.get_messages(),
            "temperature":0.0,
            "max_tokens": 65536,
            "reasoning_effort": "high",
            "response_format":{ "type": "json_object" }
        }
        
        try:
            assistant_message:dict = (await self.supplier.generate_json_ample(self.model, parameters))['choices'][0]['message']
        except Exception as e:
            self.logger.error(f"initiativeChat决策请求出错:{e}")
            
        if assistant_content := assistant_message.get('content'):
            return json.loads(assistant_content)
        else:
            return {}