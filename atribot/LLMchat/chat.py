import asyncio
import datetime
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import replace
from logging import Logger
from typing import Coroutine, Dict, List

from atribot.common_utils import download_text, extract_json_from_text, url_to_base64
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.bot_types import Context, MessageBuilder
from atribot.core.type.chat_message_type import (
    ChatMessage,
    FileMessageSegment,
    FileSegment,
    ImageSegment,
    ReplySegment,
)
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.LLM_supervisor import (
    GenerationRequestSimplify,
    GenerationResponse,
    LLMCoordinator,
    LLMSRequestFailed,
)
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.LLMchat.memory.memory_system import memorySystem
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.prepare_model_prompt import build_prompt
from atribot.LLMchat.skills.skills_manager import SkillsManager

TEXT_EXTENSIONS = {
    # 纯文本
    'txt', 'text', 'log', 'md', 'markdown', 'rst',
    # 配置文件
    'json', 'xml', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf', 'properties',
    # 数据文件
    'csv', 'tsv', 'jsonl',
    # 文档
    'html', 'htm', 'css',
    # 编程语言
    'py', 'js', 'java', 'c', 'cpp', 'php', 'rb', 'kt', 'sh', 'bash', 'bat', 'cmd', 'ps1', 'sql',
}
IMAGE_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'psd',
}


MESSAGE_DELAY = 1.5  # 多条消息间隔时间
MAX_SINGLE_MESSAGE_LENGTH = 5  # 分条发送长度阈值
LLM_COOLDOWN_THRESHOLD = 5 #间隔时间,防止多条消息同时发送
STRING_LENGTH_LIMIT = 120 #字符串长度限制

class chat_basics(ABC):
    """聊天基类"""

    def __init__(self):
        self.model_api_supervisor: LLMCoordinator = container.get("LLMSupervisor")
        self.supplier: LLMConnectionManager = container.get("LLMSupplier")
        self.memory_system: memorySystem = container.get("memorySystem")       
        self.send_message: QQAPIClient = container.get("SendMessage")
        self.chat_manager: ChatManager = container.get("ChatManager")
        self.skills:SkillsManager = container.get("SkillsManager")
        self.user_system: UserSystem = container.get("UserSystem")
        self.emoji_core: EmojiCore = container.get("EmojiCore")
        self.mcp_tool: FuncCall = container.get("MCP")
        self.config = container.get("config")
        self.log: Logger = container.get("log")
        self.build_prompt = build_prompt()
        
        self.image_classifier_supplier:universal_ai_api = self.supplier.connections[
            self.config.model.detection_image.supplier
        ].connection_object
        self.image_classifier_model:str = self.config.model.detection_image.model_name

    @abstractmethod
    async def step(self) -> None:
        """主的聊天逻辑处理的全流程"""

    @abstractmethod
    async def prompt_structure(self) -> None:
        """模型的提示词构建"""

    @abstractmethod
    async def send_reply_message_separator(self) -> None:
        """模型响应结束最终回复的阶段"""

    async def image_processing(self, image_url: str) -> str:
        """为不支持图片的model提供图片解析服务，支持多图片最大解析数量为5,

        Args:
            image_url:图像链接

        Returns:
            图片描述文本，如果没有图片则没有返回

        Raises:
            可能抛出网络请求或图片处理相关的异常
        """
        return_dict =await self.image_classifier_supplier.generate_text_lightweight(
            model = self.image_classifier_model,
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "请详细描述你看到的东西,上面是什么有什么在什么地方，如果上面有文字也要详细说清楚,如果有什么自己的理解可以说出来，如果上面是什么你认识的可以介绍一下"}
                ]
            }]
        )
        
        try:
            return return_dict['choices'][0]['message']['content']
        except Exception: 
            raise ValueError(f"识图出现错误:{return_dict}")

class GroupChat(chat_basics):
    """处理群聊天"""

    def __init__(self):
        super().__init__()
        self.model_api = self.supplier.connections[
            self.config.model.connect.supplier
        ].connection_object
        self.visual_sense = self.config.model.connect.visual_sense
        self.emoji_file_dict = self.emoji_core.emoji_file_dict
        self.api_order: list[dict[str, str]] = self.config.model.standby_model
        """备用api调用list"""
        
        self.template_request_simplify = GenerationRequestSimplify(
            model_api=self.model_api,
            model=self.config.model.connect.model_name,
            parameter=self.config.model.chat_parameter,
            messages=None
        )
        
        self.decision_function:Dict[str,Coroutine[Dict]] = {
            "speak" : self.reply_conduct,
            "update" : self.update_conduct,
            "silence" : self.silence_conduct,
            # "use_tools" : self.use_tools_conduct,
        }
        
        if self.config.model.connect.user_global_context:
            self.get_context = lambda group_id,user_id : self.chat_manager.get_private_context(user_id)
        else:
            self.get_context = lambda group_id,user_id : self.chat_manager.get_group_context(group_id)
        
    async def step(
        self,
        message: ChatMessage,
        prompt: str,
        group_id: int,
    ) -> None:
        """群聊天用的json处理版的加强版本,会携带消息中图片的位置信息"""
        
        user_id = message.user_id
        uid: str = uuid.uuid4().hex
        
        self.log.info(f"[{uid}]群LLM聊天json处理")

        await self.send_message.set_msg_emoji_like(
            message_id = message.message_id,
            # emoji_id = 183 #表情:我最可爱
            emoji_id = 66 #爱心❤
        )
        
        message_builder: MessageBuilder = await self.prompt_structure(
            message=message,
            prompt=prompt,
            group_id=group_id,
            user_id=user_id,
            including_pictures=self.visual_sense,
        )
        
        original_context:Context = await self.get_chat_context(
            group_id = group_id,
            user_id = user_id
        )#以前决策的上下文
        
        request: GenerationRequestSimplify = replace(
            self.template_request_simplify,
            increment_messages=[message_builder.build()],
            messages=original_context.get_messages(),
            tool_json=self.mcp_tool.get_func_desc_openai_style(preset=None),
            message_data=message
        )
        
        response = await self._request_model_with_fallback_(
            request = request, 
            message = message,
            prompt = prompt, 
            uid = uid
        )

        self.log.info(f"[{uid}]模型返回json_list:\n{"".join(response.reply_text)}")
        
        for response_json in (extract_json_from_text(s) for s in response.reply_text if s != ""):
            
            if isinstance(response_json, dict):
                
                for response_json in response_json.get("actions",[]):
                    
                    response_json:dict[str,str|int]
                    if decision := response_json.get("decision"):
                        
                        if fun := self.decision_function.get(decision):
                            
                            await fun(response_json, message)
                            
                        else:
                            self.log.error(f"[{uid}]无效decision:{response_json}")
                        
                    else:
                        self.log.error(f"[{uid}]返回json错误:{response_json}")
            else:
                self.log.error(f"返回json解析不正确:{type(response_json)}")
                # 错误的话考虑直接发送?
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
        
        #存储更新等,因为直接返回的是那个对象所以可以直接改变,虽然中途会有其他协程拿到这个对象改变数值但是不应堵塞其他携程的聊天
        original_context.add_user_message(f"{prompt}\n{message.llm_formatted_message}")
        original_context.extend(
            [msg for msg in response.messages if msg["role"] in ["assistant", "tool"]]
        )
        
        if response.reasoning_content:
            self.log.info(f"[{uid}]推理内容:\n{"".join(response.reasoning_content)}")
        
        self.log.info(f"[{uid}]结束json处理!")
        
        if total_tokens := response.metadata.get("total_tokens"):
            original_context.total_tokens = total_tokens#更新tiken计数
        
        if truncated_context := original_context.record_validity_check():
            try:
                if summarize_context := await self.memory_system.summarize_context(str(truncated_context)):
                    original_context.messages.insert(
                        0,
                        {"role": "assistant", "content":  summarize_context[:3000]}#简单做一个限制让这个不要太长
                    )
                    self.log.info(f"[{uid}]聊天上下文总结完成{user_id}消息:{summarize_context}")
                else:
                    self.log.info(f"[{uid}]聊天上下文总结{user_id}消息为none")
            except Exception as e:
                self.log.exception(f"[{uid}]聊天上下文信息总结出现了错误:{e}")
    
    async def prompt_structure(
        self,
        message: ChatMessage,
        prompt: str,
        group_id: int,
        user_id: int,
        including_pictures: bool,
    ) -> MessageBuilder:
        """构建提示结构

        Args:
            message: 当前传入的聊天消息
            prompt: 主要的决策提示文本
            group_id: 当前群组ID
            user_id: 当前用户ID
            including_pictures: 目标模型是否能够接收图像

        Returns:
            MessageBuilder: 包含组装好的提示负载的构建器
        """
        message_builder = MessageBuilder()
        group_history = await self.chat_manager.get_group_messages_str(group_id)

        message_builder.add_text(
            f"<group_history>{group_history[:10000]}</group_history>"
        )
        await self.append_message_segments_prompt(
            message,
            message_builder,
            including_pictures,
        )
        message_builder.add_text(
            f"<current_user_info>{await self.user_system.get_user_info(user_id)}</current_user_info>"
        )
        message_builder.add_text(
            self.build_prompt.decision_whether_responses(
                group_id=group_id,
                prompt=prompt,
                else_prompt=(
                    self.emoji_core.prompt + #表情包的提示词
                    self.skills.prompt #skills的提示词
                )
            )
        )

        return message_builder

    async def append_message_segments_prompt(
        self, 
        chat_message: ChatMessage,
        message_builder: MessageBuilder,
        including_pictures: bool,
    ) -> None:
        """为当前用户输入附加结构化的消息片段

        Args:
            chat_message: 当前传入的聊天消息
            message_builder: 用于附加内容的提示构建器
            including_pictures: 目标模型是否能够接收图像
        """
        
        Segment = chat_message.segments[0]
        quote_message = None
        data = chat_message.primeval
        message_builder.add_text(
            f"最新用户消息:\n<MESSAGE>"
            f"<user_id>{data['user_id']}</user_id>"
            f"<nick_name>{data['sender']['nickname']}</nick_name>"
            f"<group_role>{data['sender']['role']}</group_role>"
            f"<time>{time.strftime('%Y-%m-%d %H:%M:%S')}</time>\n"
            f"<message_id>{data['message_id']}</message_id>"
            "<user_message>"
        )
        
        if including_pictures:
            async def dispose_img(message:ImageSegment):
                """给自己解析图像"""
                if img := await url_to_base64(message.url,""):
                    message_builder.add_image_base64(img,"image/jpeg")
                else:
                    message_builder.add_text("[CQ:image,summary=图片出现问题]")
        else:
            async def dispose_img(message:ImageSegment):
                """交给其他模型识别图像转换文字"""
                message_builder.add_text(await self.image_processing(message.url))

        async def append_segments(segments) -> None:
            """用来统一处理对各种不同类型的消息段的加入"""
            for segment in segments:
                if isinstance(segment, FileMessageSegment):
                    if isinstance(segment, ImageSegment):
                        await dispose_img(segment)
                        continue
                    if isinstance(segment, FileSegment):
                        if file_extension := segment.file_name.split('.')[-1].lower():
                            if file_extension in IMAGE_EXTENSIONS:
                                await dispose_img(segment)
                                continue
                            elif file_extension in TEXT_EXTENSIONS:
                                message_builder.add_text(f"[CQ:file,file={segment.file_name},content={await download_text(segment.url)}]")
                                continue
                
                message_builder.add_text(segment.__str__())
        
        if isinstance(Segment,ReplySegment):
            if reply_data := await self.send_message.get_msg_details(Segment.message_id):
                quote_message = ChatMessage.from_chat_event(reply_data["data"])
                message_builder.add_text("<引用消息段>")
        
        if quote_message:
            await append_segments(quote_message.segments)
            
            message_builder.add_text("</引用消息段>")
            
            await append_segments(chat_message.segments[1:])

        else:
            await append_segments(chat_message.segments)
        
        message_builder.add_text("</user_message></MESSAGE>")
        
        if memory := [
            (
                f"user:{r[0]}",
                f"group:{r[1]}",
                datetime.datetime.fromtimestamp(r[2]).strftime("%Y-%m-%d %H:%M:%S"),
                r[2],
                f"可信度:{r[3]}"
            ) 
            for r in await self.memory_system.query_user_recently_memory(
                text = chat_message.pure_text,
                limit = 10
            )
        ] if len(chat_message.pure_text) >= 5 else False:#文本长度要大于一个值不然大概率没什么意义
            message_builder.add_text(f"以下是可能相关的最近记忆片段：<recent_memory_snippet>{memory}</recent_memory_snippet>")
    
    async def reply_conduct(self, response_json:Dict, message:ChatMessage)->None:
        
        self.log.info(f"LLM决定回复消息理由:{response_json.get("reason")}")
        group_id = message.group_id
        
        chat_condition =await self.chat_manager.get_group_LLM_decision_parameters(group_id)
        
        #更新参数
        since = chat_condition.get_seconds_since_llm_time()
        await chat_condition.update_last_time()
        
        await self.send_reply_message_separator(
            chat_text_list = response_json.get("content",[]),
            message_id = response_json.get("reply_message_id"),
            group_id = group_id,
            since_llm = since,
        )
    
    async def update_conduct(self, response_json:Dict, message:ChatMessage)->None:
        self.log.info(f"LLM决定更新用户信息理由:{response_json.get("reason")}")
        
        if user_id := response_json.get("user_id"):
            user_id = int(user_id)
        else:
            user_id = message.user_id
        
        if await self.user_system.update_user_info(
            user_id = user_id,
            current_info = await self.user_system.get_user_info(user_id),
            new_info_json = response_json.get("update_field")
        ):
            self.log.info(f"用户信息更新成功!user_id:{user_id}")
        else:
            self.log.info(f"用户信息无变化无需更新!user_id:{user_id}")
        
    
    async def silence_conduct(self, response_json:Dict, message:ChatMessage)->None:
        self.log.info(f"LLM决定静默理由:{response_json.get("reason")}")
    
    async def use_tools_conduct(self, response_json:Dict, message:ChatMessage)->None:
        self.log.info(f"LLM决定调用工具理由:{response_json.get("reason")}")


    async def _request_model_with_fallback_(
        self,
        request: GenerationRequestSimplify,
        message: ChatMessage,
        prompt: str,
        uid: str
    ) -> GenerationResponse:
        """尝试模型请求,失败时自动降级到配置的备用API

        Args:
            request (GenerationRequestSimplify): 请求体
            message (ChatMessage): 原始消息体
            prompt (str): 响应提示词
            uid (str): 唯一响应的标识

        Returns:
            GenerationResponse: 回复
        """
        try:
            return await self.model_api_supervisor.run(request)

        except LLMSRequestFailed as e:
            self.log.exception(f"[{uid}]群聊天调用工具中途出现了错误:{e}\n尝试备用api!")
            request.generation_response = e.get_response()
            
        except Exception as e:
            self.log.exception(f"[{uid}]群聊天出现了错误:{e}\n尝试备用api!")
            
        opposite_structure_increment_messages = None
        request.model_api = None
        request.parameter = { #一个绝大多数模型可用的通用配置
            "temperature":0.1,
            "top_p":0.9,
            "max_tokens": 8192,
            "tool_choice": "auto"
        }
        
        for parameter in self.api_order:
            
            supplier = parameter["supplier"]
            model_name = parameter["model_name"]
            self.log.info(f"正在使用备用api,来自{parameter}")

            visual_sense:bool = self.supplier.get_model_information(
                supplier, model_name
            ).get("visual_sense",False)

            if visual_sense == self.visual_sense:
                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                )
            else:
                if not opposite_structure_increment_messages:

                    message_builder = await self.prompt_structure(
                        message=message,
                        prompt=prompt,
                        group_id=message.group_id,
                        user_id=message.user_id,
                        including_pictures=visual_sense,
                    )
                    
                    opposite_structure_increment_messages = [message_builder.build()]

                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                    increment_messages = opposite_structure_increment_messages
                )

            try:
                return await self.model_api_supervisor.run(new_request)
            except Exception as e:
                self.log.error(f"[{uid}]备用api{parameter}出现了错误!:{e}")

        self.log.error(f"[{uid}]所有备用api出现错误!")
        raise ValueError(f"[{uid}]所有备用api出现错误!出现这个错误请联系管理员！不要再尝试使用了")


    async def get_chat_context(self, group_id:int, user_id:int)->Context:
        """获取需要的聊天

        Args:
            group_id (int): 群号
            user_id (int): 用户id

        Returns:
            Context: 上下文
        """
        return (await self.get_context(group_id,user_id)).chat_context
    
    async def send_reply_message_separator(
        self,
        chat_text_list: List[str],
        group_id: int,
        since_llm: float,
        message_id: int = None,
    ) -> None:
        """发送群文本消息，支持表情标签

        Args:
            chat_text_list (List[str]): 要解析发送的文本list
            group_id (int): 群号
            message_id (int): 回复引用消息的id
            trigger_message_id (int): 触发回复的消息id
            since_llm (float): 距离上一次llm发言时间
        """
        if not chat_text_list:
            return

        if (
            since_llm >= LLM_COOLDOWN_THRESHOLD 
            and len(chat_text_list) <= MAX_SINGLE_MESSAGE_LENGTH
            and len("".join(chat_text_list)) <= STRING_LENGTH_LIMIT
            # or MESSAGE_DELIMITER in chat_text
        ):
            # 分条发送
            
            for message in self.emoji_core.parse_list_to_cqcode_with_emotion(
                chat_text_list,
                self.emoji_file_dict,
                reply_id = message_id 
            ):
                await self.send_message.send_group_message(
                    group_id,
                    message,
                )
                await asyncio.sleep(MESSAGE_DELAY)
            return
        
        else:
            # 合并发送完
            
            await self.send_message.send_group_message(
                group_id,
                self.emoji_core.parse_text_to_cqcode_with_emotion(
                    text  = "\n".join(chat_text_list),
                    emoji_dict = self.emoji_file_dict,
                    reply_id = message_id 
                )
            )
            return
