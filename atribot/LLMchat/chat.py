from atribot.LLMchat.LLMsupervisor import (
    large_language_model_supervisor,
    GenerationRequest,
    GenerationResponse,
    LLMSRequestFailed
)
from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.LLMchat.model_api.bigModel_api import async_bigModel_api
from atribot.core.cache.management_chat_example import ChatManager
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.prepare_model_prompt import build_prompt
from atribot.LLMchat.memory.memiry_system import memorySystem
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.core.service_container import container
from atribot.LLMchat.emoji_system import emoji_core
from atribot.core.data_manage import data_manage
from typing import Dict, List, Coroutine
from atribot.core.types import RichData
from atribot.core.types import Context
from abc import ABC, abstractmethod
from atribot.common import common
from dataclasses import replace
from logging import Logger
import datetime
import asyncio



class chat_baseics(ABC):
    """聊天基类"""

    def __init__(self):
        self.model_api_supervisor: large_language_model_supervisor = container.get("LLMsupervisor")
        self.supplier: ai_connection_manager = container.get("LLMSupplier")
        self.send_message: qq_send_message = container.get("SendMessage")
        self.memiry_system: memorySystem = container.get("memirySystem")       
        self.chat_manager: ChatManager = container.get("ChatManager")
        self.user_system: UserSystem = container.get("UserSystem")
        self.emoji_core: emoji_core = container.get("EmojiCore")
        self.mcp_tool: FuncCall = container.get("MCP")
        self.log: Logger = container.get("log")
        self.config = container.get("config")
        self.build_prompt = build_prompt()
        self.bigModel: async_bigModel_api = self.supplier.connections[
            "bigModel"
        ].connection_object

    @abstractmethod
    async def step(self, data: Dict) -> None:
        """主的聊天逻辑处理

        Args:
            data (Dict): 原始消息
        """

    @abstractmethod
    def prompt_structure(self) -> str:
        """构建模型提示词"""

    @abstractmethod
    async def send_reply_message_separator(self) -> None:
        """模型响应结束最终回复部分"""

    async def image_processing(self, image_urls: list) -> str:
        """为不支持图片的model提供图片解析服务，支持多图片最大解析数量为5,

        Args:
            image_urls:包含链接的图像

        Returns:
            图片描述文本，如果没有图片则没有返回

        Raises:
            可能抛出网络请求或图片处理相关的异常
        """
        try:
            descriptions = await asyncio.gather(
                *[
                    self.bigModel.get_image_recognition(url, file_path=False)
                    for url in image_urls[:5]
                ]
            )

        except Exception as e:
            return f"user传入图片处理过程中发生错误: {str(e)}"

        self.log.info(descriptions)

        return "\n".join(
            f"<image index={idx + 1}>\n{desc}</image>"
            for idx, desc in enumerate(descriptions)
        )


class group_chat(chat_baseics):
    """处理群聊天"""

    def __init__(self):
        super().__init__()
        self.data_manage = data_manage()
        self.model_api = self.supplier.connections[
            self.config.model.connect.supplier
        ].connection_object
        self.visual_sense = self.config.model.connect.visual_sense
        self.emoji_file_dict = self.emoji_core.emoji_file_dict
        self.api_order: list[dict[str, str]] = self.config.model.standby_model
        """备用api调用list"""

        self.template_request = GenerationRequest(
            model_api=self.model_api,
            new_message="",
            messages=[],
            model=self.config.model.connect.model_name,
            system_review=self.config.model.connect.system_review,
            parameter=self.config.model.chat_parameter,
        )
        
        self.decision_function:Dict[str,Coroutine[Dict]] = {
            "reply" : self.reply_conduct,
            "update" : self.update_conduct,
            "silence" : self.silence_conduct,
            "use_tools" : self.use_tools_conduct,
        }
        
        

    async def step(self, message: RichData) -> None:
        """群聊主处理函数"""
        data = message.primeval
        group_id = data["group_id"]
        increase_context = Context()
        readable_text, img_list = await self.data_manage.data_processing_ai_chat_text(
            data
        )

        self.log.debug(f"群LLM聊天处理:{readable_text}")

        original_context = await self.chat_manager.get_group_chat(group_id)
        original_context.record_validity_check()
        group_context = await self.get_group_context(
            group_id = group_id,
            group_context = original_context,
            knowledge_base = [
                (r[0],datetime.datetime.fromtimestamp(r[1]).strftime("%Y-%m-%d %H:%M:%S"),r[2]) for r in await self.memiry_system.query_user_recently_memory(
                    text = message.pure_text
                )
            ]
        )

        user_import = self.build_prompt.build_user_Information(
            data=data, message=readable_text
        )

        increase_context.add_user_message(user_import)

        img_prompt = None
        if img_list:
            if not self.visual_sense:
                img_prompt = await self.image_processing(img_list)
            else:
                img_list = await common.urls_to_base64(img_list)

        prompt = await self.prompt_structure(
            group_id, 
            img_prompt
        )

        request = replace(
            self.template_request,
            messages=group_context,
            prompt=prompt,
            new_message=user_import,
            tool_json=self.mcp_tool.get_func_desc_openai_style(),
            # tool_json=[],
            image_url_list=img_list if (img_list and self.visual_sense) else None,
        )

        # 获取响应
        response = await self._try_model_request(request, img_list, group_id)

        chat_condition = self.chat_manager.get_group_LLM_decision_parameters(group_id)
        await chat_condition.update_trigger_user(data["user_id"])
        
        since = chat_condition.get_seconds_since_llm_time()
        await chat_condition.update_last_time()
        
        # 发送基础信息
        await self.send_reply_message_separator(
            "".join(response.reply_text), 
            group_id=group_id, 
            message_id=data["message_id"],
            since_llm=since
        )

        # 思考的信息
        if response.reasoning_content:
            await self.send_message.send_group_merge_text(
                group_id=group_id,
                message="".join(response.reasoning_content),
                source="推理内容",
            )
        
        # if reminiscence:
        #     await self.send_message.send_group_merge_text(
        #         group_id=group_id,
        #         message=str(reminiscence),
        #         source="向量查询返回",
        #     )

        # 过滤扩展list
        increase_context.extend(
            [msg for msg in response.messages if msg["role"] in ["assistant", "tool"]]
        )

        # print(response.messages)

        # 更新存储上下文
        original_context.extend(increase_context.messages)

        # print(original_context)

        await self.chat_manager.store_group_chat(group_id=group_id, context=original_context)

        self.log.debug("模型结束响应!")
        
    async def step_json(
        self, 
        message: RichData, 
        prompt:str,
        group_id: int,
    ) -> None:
        """群聊天用的json处理版"""
        
        self.log.info("群LLM聊天json处理")
        
        data = message.primeval
        group_id = data["group_id"]
        user_id = data["user_id"]

        readable_text, img_list = await self.data_manage.data_processing_ai_chat_text(
            data
        )
        
        img_prompt = None
        if img_list:
            if not self.visual_sense:
                img_prompt = await self.image_processing(img_list)
            else:
                img_list = await common.urls_to_base64(img_list)
        
        user_import = self.build_prompt.build_user_Information(
            data = data, 
            message = readable_text,
            memory = [
                (f"user_id:{r[0]}",datetime.datetime.fromtimestamp(r[1]).strftime("%Y-%m-%d %H:%M:%S"),r[2]) for r in await self.memiry_system.query_user_recently_memory(
                    text = message.pure_text,
                    limit = 10
                )
            ]
        )
        
        original_context = await self.chat_manager.get_group_chat(group_id)
        original_context.record_validity_check()
        
        request = replace(
            self.template_request,
            messages=original_context.get_messages(),
            new_message=self.prompt_structure_json(
                group_id = group_id,
                prompt = prompt,
                user_info = await self.user_system.get_user_info(user_id),
                user_import = user_import,
                chat_record = str(await self.chat_manager.get_group_messages(group_id))[:10000],
                img_prompt = img_prompt
            ),
            tool_json=self.mcp_tool.get_func_desc_openai_style(),
            image_url_list=img_list if (img_list and self.visual_sense) else None
        )
        
        response = await self._try_model_request(
            request = request, 
            group_id = group_id, 
            img_list= img_list 
        )

        self.log.info("模型返回json_list:\n"+"".join(response.reply_text))
            
        for response_json in (common.extract_json_from_text(s) for s in response.reply_text if s != ""):
            
            if isinstance(response_json, dict):
                
                for response_json in response_json.get("return",[]):
                    
                    response_json:dict[str: str|int]
                    if decision := response_json.get("decision"):
                        
                        if fun := self.decision_function.get(decision):
                            
                            await fun(response_json, data)
                            
                        else:
                            self.log.error(f"无效decision:{response_json}")
                        
                    else:
                        self.log.error(f"返回json错误:{response_json}")
            # else:
            #     # 错误的话考虑直接发送?
            #     self.log.error(f"返回json解析错误:{response_json}")
            #     chat_condition = self.chat_manager.get_group_LLM_decision_parameters(group_id)
                
            #     since = chat_condition.get_seconds_since_llm_time()
            #     await chat_condition.update_last_time()
                
            #     await self.send_reply_message_separator(
            #         chat_text = response_json,
            #         message_id = data["message_id"],
            #         group_id = group_id,
            #         since_llm = since
            #     )
            #     continue
        
        #存储更新等,因为直接返回的是那个对象所以可以直接改变
        original_context.add_user_message(prompt+user_import)
        original_context.extend(
            [msg for msg in response.messages if msg["role"] in ["assistant", "tool"]]
        )
        
        if response.reasoning_content:
            self.log.info("推理内容:\n"+ "".join(response.reasoning_content))
        
        self.log.info("结束json处理!")
        
    
    async def reply_conduct(self, response_json:Dict, data:Dict)->None:
        
        self.log.info(f"LLM决定回复消息。理由:{response_json.get("reason")}")
        group_id = data["group_id"]
        

        chat_condition = self.chat_manager.get_group_LLM_decision_parameters(group_id)
        
        since = chat_condition.get_seconds_since_llm_time()
        await chat_condition.update_last_time()
        
        await self.send_reply_message(
            chat_text_list = response_json["content"],
            message_id = response_json.get("target_message_id"),
            group_id = group_id,
            since_llm = since
        )
    
    async def update_conduct(self, response_json:Dict, data:Dict)->None:
        self.log.info(f"LLM决定更新用户信息。理由:{response_json.get("reason")}")
        
        if user_id := response_json.get("user_id"):
            pass
        else:
            user_id = data["user_id"]

        if await self.user_system.update_user_info(
            user_id = user_id,
            current_info = await self.user_system.get_user_info(user_id),
            new_info_json = response_json.get("update_field")
        ):
            self.log.info(f"用户信息更新成功!user_id:{user_id}")
        else:
            self.log.info(f"用户信息无变化无需更新!user_id:{user_id}")
        
    
    async def silence_conduct(self, response_json:Dict, data:Dict)->None:
        self.log.info(f"LLM决定静默。理由:{response_json.get("reason")}")
    
    async def use_tools_conduct(self, response_json:Dict, data:Dict)->None:
        self.log.info(f"LLM决定调用工具。理由:{response_json.get("reason")}")

    async def _try_model_request(
        self,
        request: GenerationRequest,
        img_list: List[str],
        group_id: int
    ) -> GenerationResponse:
        """尝试模型请求,失败时自动降级到配置的备用API

        Args:
            request (GenerationRequest): 请求体
            img_list (list[str]): 图像url list
            group_id (int): 群号
            reminiscence (list): 数据库查询的记忆

        Returns:
            GenerationResponse: 回复
        """
        try:
            # raise ValueError("测试用错误!")
            return await self.model_api_supervisor.step(request)

        except LLMSRequestFailed as e:
            self.log.exception(f"群聊天调用工具中途出现了错误:{e}\n尝试备用api!")
            request.generation_response = e.get_response()
            
        except Exception as e:
            self.log.exception(f"群聊天出现了错误:{e}\n尝试备用api!")
        
        cached_image_prompt = None
        request.model_api = None
        request.parameter = { #一个绝大多数模型可用的通用配置
            "temperature":0.1,
            "top_p":0.95,
            "max_tokens": 8192,
            "tool_choice": "auto"
        }
        
        for parameter in self.api_order:
            
            supplier = parameter["supplier"]
            model_name = parameter["model_name"]
            if img_list:
                visual_sense:bool = self.supplier.get_model_information(
                    supplier, model_name
                ).get("visual_sense",False)

                if visual_sense == self.visual_sense:
                    new_request = replace(
                        request,
                        model=model_name,
                        supplier_name=supplier,
                    )
                elif visual_sense:
                    new_request = replace(
                        request,
                        model=model_name,
                        supplier_name=supplier,
                        image_url_list=img_list,
                        prompt=await self.prompt_structure(
                            group_id
                        ),
                    )
                else:
                    if not cached_image_prompt:
                        cached_image_prompt = await self.prompt_structure(
                            group_id, 
                            await self.image_processing(img_list)
                        )

                    new_request = replace(
                        request,
                        model=model_name,
                        supplier_name=supplier,
                        image_url_list=[],
                        prompt=cached_image_prompt,
                    )
            else:
                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                )

            try:
                return await self.model_api_supervisor.step(new_request)
            except Exception as e:
                self.log.error(f"备用api{parameter}出现了错误!:{e}")

        self.log.error("所有备用api出现错误!")
        raise ValueError("所有备用api出现错误!出现这个错误请联系管理员！不要再尝试使用了")

    async def get_group_context(
        self, 
        group_id:int ,
        group_context:Context, 
        knowledge_base:list = []
    )->List[Dict[str, str]]:
        """构造群上下文

        Args:
            group_id (int): 群号
            group_context (Context): 群上下文对象
            knowledge_base (List): 查询的记忆,默认为空

        Returns:
            List[Dict[str, str]]: 构造好的上下文
        """
        prompt = ""
            
        prompt += f"\n\n<group_chat_history>{str(await self.chat_manager.get_group_messages(group_id))[:5000]}</group_chat_history>Please do not repeat the above information" #简单防止过长
        
        if knowledge_base:
            prompt += f"\n\n<user_memory_snippet>{knowledge_base}</user_memory_snippet>"
        
        return group_context.get_messages(prompt)
    
    
    async def prompt_structure(self, group_id: int, img_prompt: str = None) -> str:
        """提示词构造方法

        Args:
            group_id (int): 群号
            img_prompt (str): 图像提示词. Defaults to "".

        Returns:
            str: 完整提示词
        """
        prompt = self.build_prompt.group_chant_template(
            group_id,
        )
        
        if img_prompt:
            prompt += f"<image_descriptions>{img_prompt}</image_descriptions>"

        prompt += self.emoji_core.emoji_prompt

        return prompt + "Please do not repeat the above information"

    def prompt_structure_json(
        self,
        group_id:str, 
        prompt:str,
        user_import:str,
        chat_record:str,
        user_info:str,
        img_prompt:str
    )->str:
        """json处理使用的提示词构造方法

        Args:
            group_id (str): 群号
            user_import (str): 用户输入
            prompt (str): 基础prompt
            chat_record (str): 历史记录
            user_info (str): 用户信息
            img_prompt (str): 文本图像提示

        Returns:
            str: 构造完成的prompt
        """     
        return self.build_prompt.decision_whether_responses(
            group_id = group_id,
            prompt = prompt,
            chat_record = chat_record,
            else_prompt = (
                "<newest_user_import>"
                f"{f"<image_descriptions>{img_prompt}</image_descriptions>" if  img_prompt else ""}{user_import}"
                "</newest_user_import>\n"
                f"<current_user_info>{user_info}</current_user_info>"
            ) + self.emoji_core.emoji_prompt
        )
        

    async def send_reply_message_separator(
        self,
        chat_text: str,
        group_id: int,
        since_llm: float,
        message_id: int = None,
    ) -> None:
        """发送群文本消息，支持多段分割和表情标签

        Args:
            chat_text (str): 要解析发送的文本
            group_id (int): 群号
            message_id (int): 回复引用消息的id
            since_llm (float): 距离上一次llm发言时间
        """
        MESSAGE_DELAY = 1.5  # 多条消息间隔时间
        MESSAGE_DELIMITER = "$"  # 分隔符
        MAX_SINGLE_MESSAGE_LENGTH = 70  # 分条发送长度阈值
        LLM_COOLDOWN_THRESHOLD = 5 #间隔时间,防止多条消息同时发送
        
        if not (chat_text := chat_text.strip()):
            return

        if (
            len(chat_text) <= MAX_SINGLE_MESSAGE_LENGTH
            and since_llm >= LLM_COOLDOWN_THRESHOLD
            # or MESSAGE_DELIMITER in chat_text
        ):
            # 分条发送
            messages_list = self.emoji_core.parse_text_with_emotion_tags_separator(
                text=chat_text,
                emoji_dict=self.emoji_file_dict,
                separator=MESSAGE_DELIMITER,
            )
            
            if message_id:
                message = messages_list[0]
                if message['type'] == 'text':
                    await self.send_message.send_group_message(group_id, f"[CQ:reply,id={message_id}]{message['data']['text']}")
                else:
                    await self.send_message.send_group_message(
                        group_id, [{"type": "reply", "data": {"id": message_id}}, message]
                    )

                if len(messages_list) == 1:
                    return

                await asyncio.sleep(MESSAGE_DELAY)

                for message in messages_list[1:]:
                    await self.send_message.send_group_message(
                        group_id,
                        [message],
                    )
                    await asyncio.sleep(MESSAGE_DELAY)
                return
            else:
                for message in messages_list:
                    await self.send_message.send_group_message(
                        group_id,
                        [message],
                    )
                    await asyncio.sleep(MESSAGE_DELAY)
                return
        else:
            chat_text = chat_text.replace(MESSAGE_DELIMITER, "\n")
            # 合并发送完
            messages_list = self.emoji_core.parse_text_with_emotion_tags(
                chat_text, self.emoji_file_dict
            )
            if message_id:
                await self.send_message.send_group_message(
                    group_id,
                    [{"type": "reply", "data": {"id": message_id}}, *messages_list],
                )
            else:
                await self.send_message.send_group_message(
                    group_id,
                    messages_list,
                )
            return

    async def send_reply_message(
        self,
        chat_text_list: List[str],
        group_id: int,
        since_llm: float,
        message_id: int = None,
    ) -> None:
        """发送群文本消息，支持表情标签

        Args:
            chat_text (str): 要解析发送的文本
            group_id (int): 群号
            message_id (int): 回复引用消息的id
            since_llm (float): 距离上一次llm发言时间
        """
        MESSAGE_DELAY = 1.5  # 多条消息间隔时间
        MAX_SINGLE_MESSAGE_LENGTH = 4  # 分条发送长度阈值
        LLM_COOLDOWN_THRESHOLD = 5 #间隔时间,防止多条消息同时发送
        
        if not chat_text_list:
            return

        if (
            len(chat_text_list) <= MAX_SINGLE_MESSAGE_LENGTH
            and since_llm >= LLM_COOLDOWN_THRESHOLD
            # or MESSAGE_DELIMITER in chat_text
        ):
            # 分条发送
            messages_list = self.emoji_core.parse_list_with_emotion_tags(
                chat_text_list,
                self.emoji_file_dict
            )
            
            if message_id:
                message = messages_list[0]
                if message['type'] == 'text':
                    await self.send_message.send_group_message(group_id, f"[CQ:reply,id={message_id}]{message['data']['text']}")
                else:
                    await self.send_message.send_group_message(
                        group_id, [{"type": "reply", "data": {"id": message_id}}, message]
                    )

                if len(messages_list) == 1:
                    return

                await asyncio.sleep(MESSAGE_DELAY)

                for message in messages_list[1:]:
                    await self.send_message.send_group_message(
                        group_id,
                        [message],
                    )
                    await asyncio.sleep(MESSAGE_DELAY)
                return
            else:
                for message in messages_list:
                    await self.send_message.send_group_message(
                        group_id,
                        [message],
                    )
                    await asyncio.sleep(MESSAGE_DELAY)
                return
        else:
            chat_text = "\n".join(chat_text_list)
            # 合并发送完
            messages_list = self.emoji_core.parse_text_with_emotion_tags(
                chat_text, self.emoji_file_dict
            )
            if message_id:
                await self.send_message.send_group_message(
                    group_id,
                    [{"type": "reply", "data": {"id": message_id}}, *messages_list],
                )
            else:
                await self.send_message.send_group_message(
                    group_id,
                    messages_list,
                )
            return