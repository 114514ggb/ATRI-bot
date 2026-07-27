import random
import time
from enum import Enum
from typing import Any, Dict, List, Tuple, Union

import ahocorasick

from atribot.common_utils import construction_message_dict
from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.event_trigger.monitoring_alike_list import monitoring_alike_list
from atribot.core.event_trigger.monitoring_have_list import monitoring_have_list
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage


class ResponseType(Enum):
    TEXT = "text"
    IMAGE = "img"
    AUDIO = "audio"
    MIXTURE = "mixture"


class string_response:
    
    def __init__(self):
        self.send_message:QQAPIClient = container.get("SendMessage")
        config:atriConfig = container.get("config")
        self.url_prefi:str = f"file://{config.file_path.img.as_posix()}"
        self.context_management: ChatManager = container.get("ChatManager")
        self._build_automaton()
    
    def _build_automaton(self):
        """构建AC自动机"""
        self.automaton = ahocorasick.Automaton()
        
        for keyword in self.monitoring_have_list.keys():
            self.automaton.add_word(keyword, keyword)
        
        self.automaton.make_automaton()
        
    async def manage(self, message:ChatMessage, data) -> bool:
        """主处理逻辑"""
        group_id = message.group_id
        
        async def send(send_type, document):
            if send_type is ResponseType.TEXT:
                await self.send_message.send_group_msg(group_id, document)
            elif send_type is ResponseType.IMAGE:
                await self.send_message.send_group_pictures(group_id, document, True)
            elif send_type is ResponseType.AUDIO:
                await self.send_message.send_group_audio(group_id, document, True)
            elif send_type is ResponseType.MIXTURE:
                await self.send_message.send_group_msg(group_id, construction_message_dict(document,self.url_prefi))
        
        if time.time() - (await self.context_management.get_group_context(group_id)).last_msg_at < 5:
            #如果间隔太短不处理
            return False
        
        if template := self.process_string(data['raw_message']):
            send_type, document = template
            await send(send_type, document)
            return True
        return False
        
    def process_string(self, text: str) -> Tuple[ResponseType, Union[str, List[str], Dict[str, Any]]] | None:
        """
        处理字符串，返回匹配的配置
        
        Args:
            text: 输入的字符串
            
        Returns:
            如果匹配成功，返回 (ResponseType, 对应的内容)
            如果没有匹配，返回 None
        """
        if text in self.monitoring_alike_list:
            return self._get_random_response(self.monitoring_alike_list[text])
        
        for _, keyword in self.automaton.iter(text):
            if keyword in self.monitoring_have_list:
                return self._get_random_response(self.monitoring_have_list[keyword])
        
        return None
    
    def _get_random_response(self, config_list: List[List]) -> Tuple[ResponseType, Union[str, List[str], Dict[str, Any]]]:
        """
        从配置列表中随机选择一个返回
        
        Args:
            config_list: 配置列表，格式为 [["type", [content]], ...]
            
        Returns:
            (ResponseType, 对应的内容)
        """
        selected_config = random.choice(config_list)
        response_type_str = selected_config[0]
        content_list = selected_config[1]
        

        response_type = ResponseType(response_type_str)
        
        if response_type == ResponseType.MIXTURE:
            return response_type, random.choice(content_list)
        else:
            if len(content_list) == 1:
                return response_type, content_list[0]
            else:
                return response_type, random.choice(content_list)
    
    def add_alike_config(self, keyword: str, config: List[List]):
        """
        添加完全匹配配置
        
        Args:
            keyword: 关键词
            config: 配置列表
        """
        self.monitoring_alike_list[keyword] = config
    
    def add_have_config(self, keyword: str, config: List[List]):
        """
        添加包含匹配配置
        
        Args:
            keyword: 关键词
            config: 配置列表
        """
        self.monitoring_have_list[keyword] = config
        self._build_automaton()
    
    def remove_config(self, keyword: str, config_type: str = "both"):
        """
        删除配置
        
        Args:
            keyword: 要删除的关键词
            config_type: "alike", "have", "both"
        """
        if config_type in ["alike", "both"]:
            self.monitoring_alike_list.pop(keyword, None)
        
        if config_type in ["have", "both"]:
            self.monitoring_have_list.pop(keyword, None)
            self._build_automaton()
            
    monitoring_alike_list = monitoring_alike_list
    monitoring_have_list = monitoring_have_list
        

# if __name__ == "__main__":
#     s = string_response()
#     s.manage(123,{'raw_message': '高性能'})