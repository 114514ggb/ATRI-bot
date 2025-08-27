from atribot.LLMchat.LLMsupervisor import large_language_model_supervisor, GenerationRequest, GenerationResponse
from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.LLMchat.model_api.bigModel_api import async_bigModel_api
from atribot.core.cache.message_buffer_memory import message_cache
from atribot.core.cache.chan_context import context_management
from atribot.LLMchat.prepare_model_prompt import build_prompt
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.core.service_container import container
from atribot.LLMchat.emoji_system import emoji_core
from atribot.core.data_manage import data_manage
from atribot.core.types import Context
from abc import ABC, abstractmethod
from dataclasses import replace
from logging import Logger
from typing import Dict
import asyncio


class chat_baseics(ABC):
    """聊天基类"""
    def __init__(self):
        self.model_api_supervisor:large_language_model_supervisor = container.get("LLMsupervisor")
        self.supplier:ai_connection_manager = container.get("LLMSupplier")
        self.messages_cache:message_cache = container.get("MessageCache")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.context:context_management = container.get("ChatContext") 
        self.emoji_core:emoji_core = container.get("EmojiCore")
        self.mcp_tool:FuncCall = container.get("MCP")
        self.log:Logger = container.get("log")
        self.config = container.get("config")
        self.build_prompt = build_prompt()
        self.bigModel:async_bigModel_api = self.supplier.connections["bigModel"].connection_object

    
    @abstractmethod
    async def step(self, data:Dict)->None:
        """主的聊天逻辑处理

        Args:
            data (Dict): 原始消息
        """
        
    @abstractmethod
    def prompt_structure(self)->str:
        """构建模型提示词"""
    
    @abstractmethod
    async def send_reply_message(self)->None:
        """模型响应结束最终回复部分"""
        
    async def image_processing(self,image_urls:list)->str:
        """为不支持图片的model提供图片解析服务，支持多图片最大解析数量为5,
    
            Args:
                image_urls:包含链接的图像
                
            Returns:
                图片描述文本，如果没有图片则没有返回
                
            Raises:
                可能抛出网络请求或图片处理相关的异常
        """
        try:

            descriptions = await asyncio.gather(*[
                self.bigModel.get_image_recognition(url, file_path=False)
                for url in image_urls[:5]
            ])
            
        except Exception as e:
            return f"user传入图片处理过程中发生错误: {str(e)}"
        
        self.log.info(descriptions)
        
        return "\n".join(
            f"<image index={idx+1}>\n{desc}</image>"
            for idx, desc in enumerate(descriptions)
        )
        
class group_chat(chat_baseics):
    """处理群聊天"""
    
    def __init__(self):
        super().__init__()
        self.data_manage = data_manage()
        self.model_api = self.supplier.connections[self.config.model.connect.supplier].connection_object
        self.visual_sense = self.config.model.connect.visual_sense

        self.template_request = GenerationRequest(
            model_api = self.model_api,
            new_message = "",
            messages = [],
            model = self.config.model.connect.model_name,
            system_review = self.config.model.connect.system_review,
            parameter = self.config.model.chat_parameter
        )
        
    async def step(self, data:Dict)->None:
        
        
        group_id = data['group_id']
        increase_context = Context()
        readable_text,img_list = await self.data_manage.data_processing_ai_chat_text(data)
        
        self.log.debug(f"群聊天处理:{readable_text}")
        
        original_context = await self.context.get_group_chat(group_id)
        original_context.record_validity_check()
        group_context = original_context.get_messages()
        
        user_import = self.build_prompt.build_user_Information(
            data = data,
            message = readable_text
        ) 
        
        increase_context.add_user_message(user_import)
        
        img_prompt = None
        if img_list and not self.visual_sense:
            img_prompt = await self.image_processing(img_list)
        
        prompt = await self.prompt_structure(group_id, img_prompt)
        
        request = replace(
            self.template_request,
            messages=group_context,
            prompt=prompt,
            new_message=user_import,
            tool_json=self.mcp_tool.get_func_desc_openai_style(),
            image_url_list=img_list if (img_list and self.visual_sense) else None
        )
        
        #获取响应
        response = await self._try_model_request(
            request, 
            group_context, 
            user_import, 
            img_list, 
            group_id,
            img_prompt
        )

        #发送
        await self.send_reply_message(
            response.reply_text,
            group_id = group_id,
            message_id = data["message_id"]
        )
        
        #过滤扩展
        increase_context.extend([msg for msg in response.messages if msg["role"] in ["assistant", "tool"]])
        
        #更新存储上下文
        original_context.extend(increase_context.get_messages())
        await self.context.store_group_chat(
            group_id = group_id,
            context = original_context
        )
        
        self.log.debug("模型结束响应!")
        
            
    async def _try_model_request(
        self, 
        request: GenerationRequest, 
        group_context: list, 
        user_import: str, 
        img_list: list[str], 
        group_id: int, 
        img_prompt: str,
    )->GenerationResponse:
        """尝试模型请求，失败时自动降级到备用API

        Args:
            request (GenerationRequest): 请求体
            group_context (list): ai的上下文
            user_import (str): 提示
            img_list (list[str]): 图像url list
            group_id (int): 群号
            img_prompt (str): 图像提示

        Returns:
            GenerationResponse: 回复
        """
        try:
            response = await self.model_api_supervisor.step(request)
            return response
            
        except Exception as e:
            self.log.error(
                f"错误上下文:{group_context}\nuser输入:{user_import}\n"
                f"群聊天出现了错误:{e}\n尝试备用api!"
            )
            
            fallback_prompt = await self.prompt_structure(group_id, await self.image_processing(img_list)) if (img_list and self.visual_sense) else img_prompt
            
            fallback_request = replace(
                request,
                model="GLM-4.5-Flash",
                prompt=fallback_prompt,
                model_api=self.bigModel,
                image_url_list=None
            )
            
            response = await self.model_api_supervisor.step(fallback_request)
            return response
        
    async def prompt_structure(self, group_id:int, img_prompt:str)->str:
        """提示词构造方法

        Args:
            group_id (int): 群号
            img_prompt (str, optional): 图像提示词. Defaults to "".

        Returns:
            str: 完整提示词
        """
        
        prompt = self.build_prompt.group_chant_template(
            group_id,
            chat_history = await self.messages_cache.get_group_messages(group_id)
        )
        
        if img_prompt:
            prompt += f"<image_descriptions>{img_prompt}</image_descriptions>"
            
        prompt += self.emoji_core.emoji_prompt
        
        return prompt + "Please do not repeat the above information"
    
    
    async def send_reply_message(
        self,
        chat_text: str,
        group_id: int,
        message_id: int,
    ) -> None:
        """发送群文本消息，支持多段分割和表情标签

        Args:
            chat_text (str): 要解析发送的文本
            group_id (int): 群号
            message_id (int): 输入消息的id
        """
        MESSAGE_DELAY = 0.8 #多条消息间隔时间
        MESSAGE_DELIMITER = "$" #分隔符

        if not (chat_text := chat_text.strip()):
            return 
        
        if len(chat_text) <= 150 or MESSAGE_DELIMITER in chat_text:
            #分条发送
            messages_list = self.emoji_core.parse_text_with_emotion_tags_separator(
                text = chat_text, 
                emoji_dict = self.emoji_core.emoji_file_dict, 
                separator = MESSAGE_DELIMITER
            )
            # [CQ:reply,id={message_id}]
            for message in messages_list:
                await self.send_message.send_group_message(
                    group_id,
                    message["data"]["text"] if message["type"] == "text" else [message]
                )
                await asyncio.sleep(MESSAGE_DELAY)
        else:
            #合并发送完
            messages_list = self.emoji_core.parse_text_with_emotion_tags(
                chat_text, 
                self.emoji_core.emoji_file_dict
            )
            await self.send_message.send_group_message(
                group_id,
                [
                    {
                    "type": "reply",
                    "data": {
                        "id": message_id
                        }
                    },
                    *messages_list
                ]
            )
