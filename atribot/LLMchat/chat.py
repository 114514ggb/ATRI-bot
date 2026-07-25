import datetime
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import replace
from logging import Logger
from typing import Coroutine, Dict, List

from atribot.common_utils import download_text, extract_json_from_text, url_to_audio_base64, url_to_base64
from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.platform.onebot.message_event import OneBotMessageEvent
from atribot.core.platform.send_client import SendClientBase
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.core.type.chat_message_types import (
    ChatMessage,
    FileMessageSegment,
    FileSegment,
    ImageSegment,
    MessageSegment,
    RecordSegment,
    ReplySegment,
    VideoSegment,
)
from atribot.core.type.context_types import Context, MessageBuilder
from atribot.core.type.onebot_event_types import GroupMessageEvent
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.LLM_supervisor import (
    GenerationRequestSimplify,
    GenerationResponse,
    LLMCoordinator,
    LLMSRequestFailed,
)
from atribot.LLMchat.MCP.tool_calls import ToolCalls
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.memory.memory_system import MemorySystem
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.prepare_model_prompt import build_prompt
from atribot.LLMchat.skills.skills_manager import SkillsManager
from atribot.LLMchat.token_manage import TokenManager

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
MAX_SINGLE_MESSAGE_LENGTH = 4  # 分条发送长度阈值
LLM_COOLDOWN_THRESHOLD = 5 #间隔时间,防止多条消息同时发送
STRING_LENGTH_LIMIT = 500 #字符串长度限制

class ChatBasics(ABC):
    """聊天基类"""

    def __init__(
        self,
        llm_supervisor: LLMCoordinator,
        media_processor: MediaProcessor,
        llm_supplier: LLMConnectionManager,
        memory_system: MemorySystem,
        token_manager: TokenManager,
        chat_manager: ChatManager,
        skills_manager: SkillsManager,
        user_system: UserSystem,
        emoji_core: EmojiCore,
        tool_calls_mgr: ToolCalls,
        config: atriConfig,
        log: Logger,
    ):
        self.model_api_supervisor: LLMCoordinator = llm_supervisor
        self.media_processor: MediaProcessor = media_processor
        self.supplier: LLMConnectionManager = llm_supplier
        self.memory_system: MemorySystem = memory_system
        self.token_manager: TokenManager = token_manager
        self.chat_manager: ChatManager = chat_manager
        self.skills: SkillsManager = skills_manager
        self.user_system: UserSystem = user_system
        self.emoji_core: EmojiCore = emoji_core
        self.tool_calls: ToolCalls = tool_calls_mgr
        self.config: atriConfig = config
        self.log: Logger = log
        self.build_prompt = build_prompt()

    @abstractmethod
    async def step(self) -> None:
        """主的聊天逻辑处理的全流程"""

    @abstractmethod
    async def prompt_structure(self) -> None:
        """模型的提示词构建"""

    @abstractmethod
    async def send_reply_message_separator(self) -> None:
        """模型响应结束最终回复的阶段"""

    @abstractmethod
    async def trigger_internal_thought(
        self,
        custom_prompt: str,
        event: GroupMessageEvent,
        send_client:SendClientBase = None,
    ) -> None:
        """系统内部触发思考的入口"""

    async def update_conduct(self, response_json: Dict, event: MessageEventEnvelope) -> None:
        """更新用户信息（通用）"""
        self.log.info(f"LLM决定更新用户信息理由:{response_json.get('reason')}")

        if user_id := response_json.get("user_id"):
            user_id = int(user_id)
        else:
            user_id = event.user_id

        if await self.user_system.update_user_info(
            user_id=user_id,
            current_info=await self.user_system.get_user_info(user_id),
            new_info_json=response_json.get("update_field"),
        ):
            self.log.info(f"用户信息更新成功!user_id:{user_id}")
        else:
            self.log.info(f"用户信息无变化无需更新!user_id:{user_id}")

    async def silence_conduct(self, response_json: Dict, event: MessageEventEnvelope) -> None:
        """保持沉默（通用）"""
        self.log.info(f"LLM决定静默理由:{response_json.get('reason')}")

    async def append_message_segments_prompt(
        self,
        event: MessageEventEnvelope,
        message_builder: MessageBuilder,
        including_pictures: bool,
        including_audios: bool = False,
        including_videos: bool = False,
    ) -> None:
        """为当前用户输入附加结构化的消息片段"""
        Segment = event.event.segments[0]
        quote_message = None
        message_builder.add_text(
            f"最新用户消息:\n<MESSAGE>"
            f"<user_id>{event.user_id}</user_id>"
            f"<nick_name>{event.event.sender['nickname']}</nick_name>"
            f"<group_role>{event.event.sender['role']}</group_role>"
            f"<time>{time.strftime('%Y-%m-%d %H:%M:%S')}</time>\n"
            f"<message_id>{event.event.message_id}</message_id>"
            "<user_message>"
        )

        if including_pictures:
            async def dispose_img(message: ImageSegment):
                if img := await url_to_base64(message.url, ""):
                    message_builder.add_image_base64(img, "image/jpeg")
                else:
                    message_builder.add_text("[CQ:image,summary=图片出现问题]")
        else:
            async def dispose_img(message: ImageSegment):
                Image_description_text = await self.media_processor.image_to_text(message.url)
                self.log.info(f"图像识别文本结果:{Image_description_text}")
                message_builder.add_text(f"[CQ:image,summary:{Image_description_text}]")

        if including_audios:
            async def dispose_audio(segment: RecordSegment) -> None:
                audio_url = segment.url or segment.file.file
                try:
                    b64, fmt = await url_to_audio_base64(audio_url, segment.file_name)
                    message_builder.add_audio(b64, fmt)
                except Exception as e:
                    self.log.warning(f"音频下载失败，降级为文本识别: {e}")
                    desc = await self.media_processor.audio_to_text(audio_url)
                    self.log.info(f"音频识别文本结果:{desc}")
                    message_builder.add_text(f"[CQ:record,summary:{desc}]")
        else:
            async def dispose_audio(segment: RecordSegment) -> None:
                audio_url = segment.url or segment.file.file
                desc = await self.media_processor.audio_to_text(audio_url)
                self.log.info(f"音频识别文本结果:{desc}")
                message_builder.add_text(f"[CQ:record,summary:{desc}]")

        if including_videos:
            async def dispose_video(segment: VideoSegment) -> None:
                video_url = segment.url or segment.file.file
                message_builder.add_video(video_url)
        else:
            async def dispose_video(segment: VideoSegment) -> None:
                video_url = segment.url or segment.file.file
                desc = await self.media_processor.video_to_text(video_url)
                self.log.info(f"视频识别文本结果:{desc}")
                message_builder.add_text(f"[CQ:video,summary:{desc}]")

        async def append_segments(segments:List[MessageSegment]) -> None:
            for segment in segments:
                if isinstance(segment, FileMessageSegment):
                    if isinstance(segment, ImageSegment):
                        await dispose_img(segment)
                        continue
                    if isinstance(segment, RecordSegment):
                        await dispose_audio(segment)
                        continue
                    if isinstance(segment, VideoSegment):
                        await dispose_video(segment)
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

        if isinstance(Segment, ReplySegment):
            if reply_data := await event.send_client.get_msg_details(Segment.message_id):
                quote_message = ChatMessage.from_chat_event(reply_data["data"])
                message_builder.add_text("<引用消息段>")
            else:
                message_builder.add_text("<引用消息段>[引用消息解析失败]</引用消息段>")

        if quote_message:
            await append_segments(quote_message.segments)
            message_builder.add_text("</引用消息段>")
            await append_segments(event.event.segments[1:])
        else:
            await append_segments(event.event.segments)

        message_builder.add_text("</user_message></MESSAGE>")

        if (
            len(event.event.pure_text) >= 5
            and (memory := [
                (
                    f"user:{r[0]}",
                    f"group:{r[1]}",
                    datetime.datetime.fromtimestamp(r[2]).strftime("%Y-%m-%d %H:%M:%S"),
                    r[2],
                    f"可信度:{r[3]}",
                )
                for r in await self.memory_system.query_user_recently_memory(
                    user=event.user_id,
                    text=event.event.pure_text,
                    limit=10,
                )
            ])
        ):
            message_builder.add_text(
                f"以下是可能相关的最近记忆片段:<recent_memory_snippet>{memory}</recent_memory_snippet>"
            )


class GroupChat(ChatBasics):
    """处理群聊天"""

    def __init__(
        self,
        llm_supervisor: LLMCoordinator,
        media_processor: MediaProcessor,
        llm_supplier: LLMConnectionManager,
        memory_system: MemorySystem,
        token_manager: TokenManager,
        chat_manager: ChatManager,
        skills_manager: SkillsManager,
        user_system: UserSystem,
        emoji_core: EmojiCore,
        tool_calls_mgr: ToolCalls,
        config: atriConfig,
        log: Logger,
    ):
        super().__init__(
            llm_supervisor=llm_supervisor,
            media_processor=media_processor,
            llm_supplier=llm_supplier,
            memory_system=memory_system,
            token_manager=token_manager,
            chat_manager=chat_manager,
            skills_manager=skills_manager,
            user_system=user_system,
            emoji_core=emoji_core,
            tool_calls_mgr=tool_calls_mgr,
            config=config,
            log=log,
        )
        model_supplier = self.supplier.connections[
            self.config.model.connect.supplier
        ]
        model_name = self.config.model.connect.model_name
        self.model_api = model_supplier.connection_object
        model_information_dict = model_supplier.model_dict[model_name]
        self.visual_sense = model_information_dict.get("visual_sense", False)
        self.audio_sense = model_information_dict.get("audio_sense", False)
        self.video_sense = model_information_dict.get("video_sense", False)
        self.emoji_file_dict = self.emoji_core.emoji_file_dict
        
        self.api_order: list[dict[str, str]] = self.config.model.standby_model
        """备用api调用list"""
        
        self.template_request_simplify = GenerationRequestSimplify(
            model_api=self.model_api,
            model=model_name,
            parameter=self.config.model.chat_parameter,
            messages=None,
            visual_sense=self.visual_sense,
            audio_sense=self.audio_sense,
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
        event: MessageEventEnvelope,
        prompt: str,
        group_id: int,
    ) -> None:
        """群聊天用的json处理版的加强版本,会携带消息中图片的位置信息"""
        
        user_id = event.user_id
        uid: str = uuid.uuid4().hex
        
        self.log.info(f"[{uid}]群LLM聊天json处理")

        await event.send_client.set_msg_emoji_like(
            message_id = event.event.message_id,
            # emoji_id = 183 #表情:我最可爱
            emoji_id = 66 #爱心❤
        )
        #181 茶
        
        message_builder: MessageBuilder = await self.prompt_structure(
            message=event,
            prompt=prompt,
            group_id=group_id,
            user_id=user_id,
            including_pictures=self.visual_sense,
            including_audios=self.audio_sense,
            including_videos=self.video_sense,
        )
        
        original_context:Context = await self.get_chat_context(
            group_id = group_id,
            user_id = user_id
        )#以前决策的上下文
        
        request: GenerationRequestSimplify = replace(
            self.template_request_simplify,
            increment_messages=[message_builder.build()],
            messages=original_context.get_messages(),
            tool_json=self.tool_calls.get_func_desc_openai_style(preset="group_chat"),
            message_data=event
        )
        
        response = await self._request_model_with_fallback_(
            request = request, 
            event = event,
            prompt = prompt, 
            uid = uid
        )

        self.log.info(f"[{uid}]模型返回json_list:\n{"".join(response.reply_text)}")
        
        async def execute_response_json(response_json:dict):
            if decision := response_json.get("decision"):
                
                if fun := self.decision_function.get(decision):
                    
                    await fun(response_json, event)
                    
                else:
                    self.log.error(f"[{uid}]无效decision:{response_json}")
                
            else:
                self.log.error(f"[{uid}]返回json错误:{response_json}")
        
        for response_json in (extract_json_from_text(s) for s in response.reply_text if s != ""):
            
            if isinstance(response_json, dict):
                
                if response_list := response_json.get("actions"):
                
                    for response_json in response_list:
                        
                        await execute_response_json(response_json)
                        
                else:
                    await execute_response_json(response_json)
                    
            else:
                self.log.error(f"返回json解析不正确:{type(response_json)}")
                event.send_client.send_group_merge_text(
                    group_id = group_id,
                    message = f"无法解析的错误返回值:\n{response_json}",
                    source = "模型返回无法解析的格式",
                )
        
        #存储更新等,因为直接返回的是那个对象所以可以直接改变,虽然中途会有其他协程拿到这个对象改变数值但是不应堵塞其他携程的聊天
        original_context.add_user_message(f"{prompt}\n最新用户消息:{event.llm_formatted_message}")
        original_context.extend(
            [msg for msg in response.messages if msg["role"] in ["assistant", "tool"]]
        )
        
        if response.reasoning_content:
            self.log.info(f"[{uid}]推理内容:\n{"".join(response.reasoning_content)}")
        
        self.log.info(f"[{uid}]结束json处理!")
        
        if total_tokens := response.metadata.get("total_tokens"):
            original_context.total_tokens = total_tokens#更新tiken计数
            try:
                await self.token_manager.record_token_usage(
                    user_id=event.user_id,
                    group_id=event.group_id,
                    prompt_tokens=response.metadata.get("prompt_tokens", 0),
                    completion_tokens=response.metadata.get("completion_tokens", 0),
                    total_tokens=total_tokens,
                    model_name=response.model
                )
            except Exception as e:
                self.log.error(f"[{uid}]记录token使用失败: {e}")
        else:
            original_context.total_tokens = original_context.count_estimate_tokens()
        
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

    async def trigger_internal_thought(
        self,
        custom_prompt: str,
        event: OneBotMessageEvent,
    ) -> None:
        """系统内部触发思考的入口

        Args:
            custom_prompt: 触发提示词
            event: OneBotMessageEvent
            send_client: 发送客户端，必须传入
        """
        uid: str = uuid.uuid4().hex
        self.log.info(f"[{uid}]群LLM事件通知触发处理")

        group_id = event.group_id
        user_id = event.user_id or None

        message_builder = MessageBuilder()
        group_history = await self.chat_manager.get_group_messages_str(group_id)

        message_builder.add_text(
            self.skills.prompt #skills的提示词
        )
        message_builder.add_text(
            f"<group_history>{group_history[:10000]}</group_history>"
        )

        prompt =(
            f"{custom_prompt}\n触发定时消息用户:<user_id>{user_id}</user_id>"
            f"<current_user_info>{await self.user_system.get_user_info(user_id)}</current_user_info>" if user_id else ""
        )
        
        message_builder.add_text(
            self.build_prompt.decision_whether_responses(
                group_id=group_id,
                prompt=prompt,
                else_prompt=self.emoji_core.prompt
            )
        )

        if user_id:
            #如果一个user触发了定时，那么应该在他的上下文消息里
            original_context = await self.get_chat_context(
                group_id = group_id,
                user_id = user_id
            )
        else:
            original_context = self.chat_manager.get_group_context(group_id)
            
        request: GenerationRequestSimplify = replace(
            self.template_request_simplify,
            increment_messages=[message_builder.build()],
            messages=original_context.get_messages(),
            tool_json=self.tool_calls.get_func_desc_openai_style(preset="group_chat"),
            message_data=event
        )
        
        response = await self._request_model_with_fallback_(
            request = request, 
            event = event,
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
                            
                            await fun(response_json, event)
                            
                        else:
                            self.log.error(f"[{uid}]无效decision:{response_json}")
                        
                    else:
                        self.log.error(f"[{uid}]返回json错误:{response_json}")
            else:
                self.log.error(f"返回json解析不正确:{type(response_json)}")

        original_context.add_user_message(prompt)
        original_context.extend(
            [msg for msg in response.messages if msg["role"] in ["assistant", "tool"]]
        )
        
        if response.reasoning_content:
            self.log.info(f"[{uid}]推理内容:\n{"".join(response.reasoning_content)}")
        
        self.log.info(f"[{uid}]结束json处理!")
        
        if total_tokens := response.metadata.get("total_tokens"):
            original_context.total_tokens = total_tokens#更新tiken计数
            try:
                await self.token_manager.record_token_usage(
                    user_id=event.user_id,
                    group_id=event.group_id,
                    prompt_tokens=response.metadata.get("prompt_tokens", 0),
                    completion_tokens=response.metadata.get("completion_tokens", 0),
                    total_tokens=total_tokens,
                    model_name=response.model
                )
            except Exception as e:
                self.log.error(f"[{uid}]记录token使用失败: {e}")
        else:
            original_context.total_tokens = original_context.count_estimate_tokens()
            
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
        event: MessageEventEnvelope,
        prompt: str,
        group_id: int,
        user_id: int,
        including_pictures: bool,
        including_audios: bool = False,
        including_videos: bool = False,
    ) -> MessageBuilder:
        """构建提示结构

        Args:
            event: 当前传入的聊天消息事件
            prompt: 主要的决策提示文本
            group_id: 当前群组ID
            user_id: 当前用户ID
            including_pictures: 目标模型是否能够接收图像
            including_audios: 目标模型是否能够接收音频
            including_videos: 目标模型是否能够接收视频

        Returns:
            MessageBuilder: 包含组装好的提示负载的构建器
        """
        message_builder = MessageBuilder()
        group_history = await self.chat_manager.get_group_messages_str(group_id)

        message_builder.add_text(
            self.skills.prompt #skills的提示词
        )
        message_builder.add_text(
            f"<group_history>{group_history[:10000]}</group_history>"
        )
        await self.append_message_segments_prompt(
            event,
            message_builder,
            including_pictures,
            including_audios,
            including_videos,
        )
        message_builder.add_text(
            f"<current_user_info>{await self.user_system.get_user_info(user_id)}</current_user_info>"
        )
        message_builder.add_text(
            self.build_prompt.decision_whether_responses(
                group_id=group_id,
                prompt=prompt,
                else_prompt=self.emoji_core.prompt#表情包的提示词
            )
        )

        return message_builder

    async def append_message_segments_prompt(
        self, 
        event: MessageEventEnvelope,
        message_builder: MessageBuilder,
        including_pictures: bool,
        including_audios: bool = False,
        including_videos: bool = False,
    ) -> None:
        """为当前用户输入附加结构化的消息片段

        Args:
            event: 当前传入的聊天消息事件
            message_builder: 用于附加内容的提示构建器
            including_pictures: 目标模型是否能够接收图像
            including_audios: 目标模型是否能够接收音频
            including_videos: 目标模型是否能够接收视频
        """
        
        Segment = event.event.segments[0]
        quote_message = None

        message_builder.add_text(
            f"最新用户消息:\n<MESSAGE>"
            f"<user_id>{event.user_id}</user_id>"
            f"<nick_name>{event.event.sender['nickname']}</nick_name>"
            f"<group_role>{event.event.sender['role']}</group_role>"
            f"<time>{time.strftime('%Y-%m-%d %H:%M:%S')}</time>\n"
            f"<message_id>{event.event.message_id}</message_id>"
            "<user_message>"
        )
        
        if including_pictures:
            async def dispose_img(message:ImageSegment):
                """给自己解析图像"""
                if img := await url_to_base64(message.url, ""):
                    message_builder.add_image_base64(img,"image/jpeg")
                else:
                    message_builder.add_text("[CQ:image,summary=图片下载出现问题]")
        else:
            async def dispose_img(message:ImageSegment):
                """交给其他模型识别图像转换文字"""
                Image_description_text = await self.media_processor.image_to_text(message.url)
                self.log.info(f"输入图片描述:{Image_description_text}]")
                message_builder.add_text(f"[CQ:image,summary:{Image_description_text}]")

        if including_audios:
            async def dispose_audio(segment: RecordSegment) -> None:
                """直接将音频以 base64 嵌入，下载失败时降级为文本识别"""
                audio_url = segment.url or segment.file.file
                try:
                    b64, fmt = await url_to_audio_base64(audio_url, segment.file_name)
                    message_builder.add_audio(b64, fmt)
                except Exception as e:
                    self.log.warning(f"音频下载失败，降级为文本识别: {e}")
                    desc = await self.media_processor.audio_to_text(audio_url)
                    message_builder.add_text(f"[CQ:record,summary:{desc}]")
        else:
            async def dispose_audio(segment: RecordSegment) -> None:
                """交给其他模型将音频转为文字"""
                audio_url = segment.url or segment.file.file
                desc = await self.media_processor.audio_to_text(audio_url)
                self.log.info(f"音频识别:{desc}]")
                message_builder.add_text(f"[CQ:record,summary:{desc}]")

        if including_videos:
            async def dispose_video(segment: VideoSegment) -> None:
                """直接传入视频 URL 供模型理解"""
                video_url = segment.url or segment.file.file
                message_builder.add_video(video_url)
        else:
            async def dispose_video(segment: VideoSegment) -> None:
                """交给其他模型将视频转为文字"""
                video_url = segment.url or segment.file.file
                desc = await self.media_processor.video_to_text(video_url)
                self.log.info(f"视频识别结果:{desc}")
                message_builder.add_text(f"[CQ:video,summary:{desc}]")

        async def append_segments(segments) -> None:
            """用来统一处理对各种不同类型的消息段的加入"""
            for segment in segments:
                if isinstance(segment, FileMessageSegment):
                    if isinstance(segment, ImageSegment):
                        await dispose_img(segment)
                        continue
                    if isinstance(segment, RecordSegment):
                        await dispose_audio(segment)
                        continue
                    if isinstance(segment, VideoSegment):
                        await dispose_video(segment)
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
            if reply_data := await event.send_client.get_msg_details(Segment.message_id):
                quote_message = ChatMessage.from_chat_event(reply_data["data"])
                message_builder.add_text("<引用消息段>")
        
        if quote_message:
            await append_segments(quote_message.segments)
            
            message_builder.add_text("</引用消息段>")
            
            await append_segments(event.event.segments[1:])

        else:
            await append_segments(event.event.segments)
        
        message_builder.add_text("</user_message></MESSAGE>")
        
        if memory := [
            (
                f"user:{r[0]}",
                f"group:{r[1]}",
                datetime.datetime.fromtimestamp(r[2]).strftime("%Y-%m-%d %H:%M:%S"),
                r[2],
                f"可信度:{r[3]}"
            ) 
            for r in await self.memory_system.query_recently_memory(
                text = event.event.pure_text,
                limit = 10
            )
        ] if len(event.event.pure_text) >= 5 else False:#文本长度要大于一个值不然大概率没什么意义
            message_builder.add_text(f"以下是可能相关的最近记忆片段:<recent_memory_snippet>{memory}</recent_memory_snippet>")
    
    async def reply_conduct(self, response_json:Dict, event:MessageEventEnvelope)->None:
        
        self.log.info(f"LLM决定回复消息理由:{response_json.get("reason")}")
        group_id = event.group_id
        
        chat_condition =await self.chat_manager.get_group_LLM_decision_parameters(group_id)
        
        #更新参数
        since = chat_condition.get_seconds_since_llm_time()
        await chat_condition.update_last_time()
        
        await self.send_reply_message_separator(
            chat_text_list = response_json.get("content",[]),
            message_id = response_json.get("reply_message_id"),
            group_id = group_id,
            since_llm = since,
            send_client=event.send_client,
        )
    
    async def use_tools_conduct(self, response_json:Dict, event:MessageEventEnvelope)->None:
        self.log.info(f"LLM决定调用工具理由:{response_json.get("reason")}")

    async def _request_model_with_fallback_(
        self,
        request: GenerationRequestSimplify,
        event: MessageEventEnvelope,
        prompt: str,
        uid: str
    ) -> GenerationResponse:
        """尝试模型请求,失败时自动降级到配置的备用API

        Args:
            request (GenerationRequestSimplify): 请求体
            event (MessageEventEnvelope): 原始消息事件
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

            model_info = self.supplier.get_model_information(supplier, model_name)
            visual_sense: bool = model_info.get("visual_sense", False)
            audio_sense: bool = model_info.get("audio_sense", False)

            if visual_sense == self.visual_sense:#只考虑图像的情况
                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                    visual_sense=visual_sense,
                    audio_sense=audio_sense,
                )
            else:
                if not opposite_structure_increment_messages:
                    #没有缓存重新构建消息
                    message_builder = await self.prompt_structure(
                        event=event,
                        prompt=prompt,
                        group_id=event.group_id,
                        user_id=event.user_id,
                        including_pictures=visual_sense,
                    )
                    
                    opposite_structure_increment_messages = [message_builder.build()]

                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                    increment_messages=opposite_structure_increment_messages,
                    visual_sense=visual_sense,
                    audio_sense=audio_sense,
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
        chat_text_list: List[str] | str,
        group_id: int,
        since_llm: float,
        message_id: int = None,
        send_client:SendClientBase = None,
    ) -> None:
        """发送群文本消息，支持表情标签

        Args:
            chat_text_list (List[str]): 要解析发送的文本list
            group_id (int): 群号
            message_id (int): 回复引用消息的id
            since_llm (float): 距离上一次llm发言时间
            send_client: SendClientBase 发送客户端，必须传入
        """

        if not chat_text_list:
            return

        if (
            since_llm >= LLM_COOLDOWN_THRESHOLD 
            and len(chat_text_list) <= MAX_SINGLE_MESSAGE_LENGTH
            and len("".join(chat_text_list)) <= STRING_LENGTH_LIMIT
            # or MESSAGE_DELIMITER in chat_text
        ):
            # 分条发送（含表情标签错误回退）
            await self.emoji_core.send_list_with_emoji_fallback(
                text_list=chat_text_list,
                emoji_dict=self.emoji_file_dict,
                send_func=lambda msg: send_client.send_group_msg(group_id, msg),
                reply_id=message_id,
                delay=MESSAGE_DELAY,
            )
            return

        else:
            # 合并发送（含表情标签错误回退）
            text = chat_text_list if isinstance(chat_text_list, str) else "\n".join(chat_text_list)
            await self.emoji_core.send_with_emoji_fallback(
                text=text,
                emoji_dict=self.emoji_file_dict,
                send_func=lambda msg: send_client.send_group_msg(group_id, msg),
                reply_id=message_id,
            )
            return


class PrivateChat(ChatBasics):
    """处理私聊天"""

    def __init__(
        self,
        llm_supervisor: LLMCoordinator,
        media_processor: MediaProcessor,
        llm_supplier: LLMConnectionManager,
        memory_system: MemorySystem,
        token_manager: TokenManager,
        chat_manager: ChatManager,
        skills_manager: SkillsManager,
        user_system: UserSystem,
        emoji_core: EmojiCore,
        tool_calls_mgr: ToolCalls,
        config: atriConfig,
        log: Logger,
    ):
        super().__init__(
            llm_supervisor=llm_supervisor,
            media_processor=media_processor,
            llm_supplier=llm_supplier,
            memory_system=memory_system,
            token_manager=token_manager,
            chat_manager=chat_manager,
            skills_manager=skills_manager,
            user_system=user_system,
            emoji_core=emoji_core,
            tool_calls_mgr=tool_calls_mgr,
            config=config,
            log=log,
        )

        model_supplier = self.supplier.connections[
            self.config.model.connect.supplier
        ]
        model_name = self.config.model.connect.model_name
        self.model_api = model_supplier.connection_object
        model_information_dict = model_supplier.model_dict[model_name]
        self.visual_sense = model_information_dict.get("visual_sense", False)
        self.audio_sense = model_information_dict.get("audio_sense", False)
        self.video_sense = model_information_dict.get("video_sense", False)
        self.emoji_file_dict = self.emoji_core.emoji_file_dict

        self.api_order: list[dict[str, str]] = self.config.model.standby_model

        self.template_request_simplify = GenerationRequestSimplify(
            model_api=self.model_api,
            model=model_name,
            parameter=self.config.model.chat_parameter,
            messages=None,
            visual_sense=self.visual_sense,
            audio_sense=self.audio_sense,
        )

    async def step(self, event: MessageEventEnvelope, prompt: str) -> None:
        """私聊 LLM 处理全流程"""
        user_id = event.user_id
        uid: str = uuid.uuid4().hex

        self.log.info(f"[{uid}]私聊LLM聊天json处理 user:{user_id}")

        message_builder: MessageBuilder = await self.prompt_structure(
            event=event,
            prompt=prompt,
            user_id=user_id,
            including_pictures=self.visual_sense,
            including_audios=self.audio_sense,
            including_videos=self.video_sense,
        )

        private_context_obj = await self.chat_manager.get_private_context(user_id)
        original_context: Context = private_context_obj.chat_context

        request: GenerationRequestSimplify = replace(
            self.template_request_simplify,
            increment_messages=[message_builder.build()],
            messages=original_context.get_messages(),
            tool_json=self.tool_calls.get_func_desc_openai_style(preset="private_chat"),
            message_data=event,
        )

        response = await self._request_model_with_fallback_private_(
            request=request,
            event=event,
            prompt=prompt,
            uid=uid,
        )

        self.log.info(f"[{uid}]私聊模型返回json_list:\n{''.join(response.reply_text)}")

        for response_json in (extract_json_from_text(s) for s in response.reply_text if s != ""):
            if isinstance(response_json, dict):
                for action in response_json.get("actions", []):
                    action: dict[str, str | int]
                    if decision := action.get("decision"):
                        if decision == "speak":
                            await self._private_speak_conduct(action, event)
                        elif decision == "update":
                            await self.update_conduct(action, event)
                        elif decision == "silence":
                            await self.silence_conduct(action, event)
                        else:
                            self.log.error(f"[{uid}]无效decision:{action}")
                    else:
                        self.log.error(f"[{uid}]返回json错误:{action}")
            else:
                self.log.error(f"[{uid}]返回json解析不正确:{type(response_json)}")

        original_context.add_user_message(f"{prompt}\n{event.llm_formatted_message}")
        original_context.extend(
            [msg for msg in response.messages if msg["role"] in ["assistant", "tool"]]
        )

        if response.reasoning_content:
            self.log.info(f"[{uid}]推理内容:\n{''.join(response.reasoning_content)}")

        self.log.info(f"[{uid}]私聊json处理结束!")

        if total_tokens := response.metadata.get("total_tokens"):
            original_context.total_tokens = total_tokens
            try:
                await self.token_manager.record_token_usage(
                    user_id=event.user_id,
                    group_id=event.group_id,
                    prompt_tokens=response.metadata.get("prompt_tokens", 0),
                    completion_tokens=response.metadata.get("completion_tokens", 0),
                    total_tokens=total_tokens,
                    model_name=response.model
                )
            except Exception as e:
                self.log.error(f"[{uid}]记录token使用失败: {e}")
        else:
            original_context.total_tokens = original_context.count_estimate_tokens()

        if truncated_context := original_context.record_validity_check():
            try:
                if summarize_context := await self.memory_system.summarize_context(str(truncated_context)):
                    original_context.messages.insert(
                        0,
                        {"role": "assistant", "content": summarize_context[:3000]},
                    )
                    self.log.info(f"[{uid}]私聊上下文总结完成 user:{user_id} 消息:{summarize_context}")
                else:
                    self.log.info(f"[{uid}]私聊上下文总结为none user:{user_id}")
            except Exception as e:
                self.log.exception(f"[{uid}]私聊上下文信息总结出现了错误:{e}")

    async def trigger_internal_thought(
        self,
        custom_prompt: str,
        user_id: int,
        group_id: int | None = None,
    ) -> None:
        """系统内部触发思考的入口"""
        raise ValueError("未实现~")

    async def prompt_structure(
        self,
        event: MessageEventEnvelope,
        prompt: str,
        user_id: int,
        including_pictures: bool,
        including_audios: bool = False,
        including_videos: bool = False,
    ) -> MessageBuilder:
        """构建私聊提示结构"""
        message_builder = MessageBuilder()

        await self.append_message_segments_prompt(
            event,
            message_builder,
            including_pictures,
            including_audios,
            including_videos,
        )
        message_builder.add_text(
            f"<current_user_info>{await self.user_system.get_user_info(user_id)}</current_user_info>"
        )
        message_builder.add_text(
            self.build_prompt.decision_whether_private_responses(
                user_id=user_id,
                prompt=prompt,
                else_prompt=(
                    self.emoji_core.prompt
                    + self.skills.prompt
                ),
            )
        )
        return message_builder

    async def _private_speak_conduct(self, response_json: Dict, event: MessageEventEnvelope) -> None:
        """发送消息决定"""
        self.log.info(f"私聊LLM决定回复 理由:{response_json.get('reason')}")
        await self.send_reply_message_separator(
            chat_text_list=response_json.get("content", []),
            user_id=event.user_id,
            send_client=event.send_client,
        )

    async def send_reply_message_separator(
        self,
        chat_text_list: List[str],
        user_id: int,
        send_client:SendClientBase = None,
    ) -> None:
        """发送私聊文本消息，支持表情标签"""

        if not chat_text_list:
            return

        if (
            len(chat_text_list) <= MAX_SINGLE_MESSAGE_LENGTH
            and len("".join(chat_text_list)) <= STRING_LENGTH_LIMIT
        ):
            await self.emoji_core.send_list_with_emoji_fallback(
                text_list=chat_text_list,
                emoji_dict=self.emoji_file_dict,
                send_func=lambda msg: send_client.send_private_msg(user_id=user_id, message=msg),
                delay=MESSAGE_DELAY,
            )
        else:
            await self.emoji_core.send_with_emoji_fallback(
                text="\n".join(chat_text_list),
                emoji_dict=self.emoji_file_dict,
                send_func=lambda msg: send_client.send_private_msg(user_id=user_id, message=msg),
            )

    async def _request_model_with_fallback_private_(
        self,
        request: GenerationRequestSimplify,
        event: MessageEventEnvelope,
        prompt: str,
        uid: str,
    ) -> GenerationResponse:
        """尝试模型请求,失败时自动降级到配置的备用API"""
        try:
            return await self.model_api_supervisor.run(request)
        except LLMSRequestFailed as e:
            self.log.exception(f"[{uid}]私聊调用出现错误:{e}\n尝试备用api!")
            request.generation_response = e.get_response()
        except Exception as e:
            self.log.exception(f"[{uid}]私聊出现了错误:{e}\n尝试备用api!")

        opposite_structure_increment_messages = None
        request.model_api = None
        request.parameter = {
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 8192,
            "tool_choice": "auto",
        }

        for parameter in self.api_order:
            supplier = parameter["supplier"]
            model_name = parameter["model_name"]
            self.log.info(f"[{uid}]私聊正在使用备用api: {parameter}")

            model_info = self.supplier.get_model_information(supplier, model_name)
            visual_sense: bool = model_info.get("visual_sense", False)
            audio_sense: bool = model_info.get("audio_sense", False)

            if visual_sense == self.visual_sense:
                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                    visual_sense=visual_sense,
                    audio_sense=audio_sense,
                )
            else:
                if not opposite_structure_increment_messages:
                    message_builder = await self.prompt_structure(
                        event=event,
                        prompt=prompt,
                        user_id=event.user_id,
                        including_pictures=visual_sense,
                    )
                    opposite_structure_increment_messages = [message_builder.build()]

                new_request = replace(
                    request,
                    model=model_name,
                    supplier_name=supplier,
                    increment_messages=opposite_structure_increment_messages,
                    visual_sense=visual_sense,
                    audio_sense=audio_sense,
                )

            try:
                return await self.model_api_supervisor.run(new_request)
            except Exception as e:
                self.log.error(f"[{uid}]私聊备用api{parameter}出现了错误!:{e}")

        self.log.error(f"[{uid}]私聊所有备用api出现错误!")
        raise ValueError(f"[{uid}]私聊所有备用api出现错误!")