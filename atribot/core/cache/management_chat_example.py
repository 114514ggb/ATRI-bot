import datetime
from logging import Logger
from typing import TYPE_CHECKING, Dict, List

from atribot.common_utils import url_to_audio_mp3, url_to_image_jpeg, url_to_video_mp4
from atribot.core.atri_config import atriConfig
from atribot.core.cache.context_lifecycle_manager import ContextLifecycleManager
from atribot.core.event_bus.rule import Rule
from atribot.core.pipeline.middleware import PipelineMiddleware
from atribot.core.platform.manager import PlatformManager
from atribot.core.service_container import ServiceBase, container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.core.type.chat_message_types import (
    ImageSegment,
    RecordSegment,
    TextSegment,
    VideoSegment,
)
from atribot.core.type.chat_types import GroupContext, LLMGroupChatCondition, PrivateContext
from atribot.core.type.context_types import Context, MessageBuilder
from atribot.core.type.onebot_event_types import (
    GroupMessageEvent,
    MessageSentEvent,
    PostType,
    PrivateMessageEvent,
)
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.memory.memory_system import MemorySystem

# 多模态历史消息默认保留数量
DEFAULT_INCLUDING_PICTURES = 2
DEFAULT_INCLUDING_AUDIOS = 1
DEFAULT_INCLUDING_VIDEOS = 1

if TYPE_CHECKING:
    from atribot.core.type.bot_types import atriMessageEvent


class ChatManager(ServiceBase):
    """管理聊天实例类（异步安全）"""
    
    @classmethod
    def factory(
        cls,
        config: atriConfig,
        time_trigger: TimeTriggerSupervisor,
        media_processor: MediaProcessor,
        log: Logger,
    ) -> ChatManager:
        return cls(
            log=log,
            time_trigger=time_trigger,
            media_processor=media_processor,
            default_play_role=config.ai_chat.playRole,
            group_messages_max_limit=config.ai_chat.group_max_record,
            private_messages_max_limit=config.ai_chat.private_max_record,
            group_LLM_max_limit=config.ai_chat.ai_max_record,
            character_folder=config.file_path.chat_manager,
            initiative_white_list=config.group_initiative_chat_white_list,
            information_extraction=config.group_information_extraction,
        )

    def __init__(
        self,
        log: Logger,
        time_trigger: TimeTriggerSupervisor,
        media_processor: MediaProcessor | None = None,
        default_play_role: str = "none",
        group_messages_max_limit: int = 20,
        private_messages_max_limit: int = 20,
        group_LLM_max_limit: int = 20,
        character_folder: str = "atribot/LLMchat/character_setting",
        initiative_white_list: List = None,
        information_extraction: List = None,
        archival_after: float = 1800.0
    ):
        self.log = log.getChild("ChatManager")
        self.time_trigger = time_trigger
        self.media_processor: MediaProcessor | None = media_processor
        self.group_dict: Dict[int, GroupContext] = {}
        """存储群组上下文实例"""
        self.private_dict:Dict[int, PrivateContext] = {}
        """存储私聊上下文实例"""
        self.default_play_role: str = default_play_role
        """默认扮演角色"""
        self.group_max_record: int = group_messages_max_limit
        """群消息最大记录数"""
        self.private_max_record: int = private_messages_max_limit
        """私聊最大记录数"""
        self.LLM_max_record: int = group_LLM_max_limit
        """LLM聊天的轮数"""
        self.character_folder: str = character_folder
        """角色设定文件夹路径"""
        self.play_role_list: Dict[str, str] = {"none": ""}
        """角色预设字典"""
        self.initiative_white_list:list = initiative_white_list if initiative_white_list else []
        """配置文件里的群主动聊天白名单(非动态)"""
        self.information_extraction:list = information_extraction if information_extraction else []
        """配置文件里的是否启用群信息提取白名单(非动态)"""
        self.lifecycle_manager = ContextLifecycleManager(archival_after = archival_after)
        """用于持久化上下文的,生命周期管理器"""
        self.time_trigger.add_task(
            task_id = 1001,
            func = self.groom_context_storage,
            trigger_delta = archival_after,
            interval = archival_after,
            remarks = "定期归档不活跃项目"
        )
        self.time_trigger.add_task(
            task_id = 1002,
            func = self.context_storage,
            trigger_delta = 480,
            interval = 480,
            remarks = "缓存全部上下文"
        )
        
        self._load_character_settings()
        
        self._mw_instance: PipelineMiddleware | None = None
        self._listener_fn = None
        self._pm: PlatformManager | None = None

    async def initialize(self) -> None:
        """初始化：注册上下文加载中间件和消息存储监听器"""
        pm = container.get_by_type(PlatformManager)
        self._pm = pm

        class _ContextLoader(PipelineMiddleware):
            name = "context_loader"
            async def process(self_, msg: atriMessageEvent) -> atriMessageEvent | None:
                return await self._context_loader(msg)

        self._mw_instance = _ContextLoader()
        await pm.pipeline.add_middleware(self._mw_instance)

        class _StoreRule(Rule):
            rule_type = "always"
            async def match(self_, msg: atriMessageEvent) -> bool:
                return isinstance(msg.event, (
                    GroupMessageEvent, PrivateMessageEvent, MessageSentEvent,
                ))

        self._listener_fn = self._store_message_context
        pm.event_bus.on(
            PostType.MESSAGE, 
            rule=_StoreRule(),
            priority = 60
        )(self._store_message_context)

    async def cleanup(self) -> None:
        """清理：注销上下文处理器"""
        if self._pm is not None:
            if self._mw_instance is not None:
                await self._pm.pipeline.remove_middleware("context_loader")
                self._mw_instance = None
            if self._listener_fn is not None:
                self._pm.event_bus.remove_listener(self._listener_fn)
                self._listener_fn = None

    async def _context_loader(self, msg: atriMessageEvent) -> atriMessageEvent | None:
        """加载上下文,更新时间窗口"""
        ev = msg.event
        group_id = msg.group_id

        if group_id is not None:
            ctx = await self.get_group_context(group_id)
            ctx.time_window.add()
            msg._extra["group_context"] = ctx
        elif isinstance(ev, PrivateMessageEvent):
            ctx = await self.get_private_context(ev.user_id)
            ctx.time_window.add()
            msg._extra["private_context"] = ctx
        
        return msg

    async def _store_message_context(self, msg: atriMessageEvent) -> None:
        """EventBus 监听器：存储消息到上下文,触发记忆总结,丢弃消息"""

        result = await self.add_message_record(msg)
        if result is None:
            return
        
        messages_str, context_obj = result
        group_id = msg.group_id
        memory_system = container.get_by_type(MemorySystem)

        if group_id is not None:
            context_obj:GroupContext
            async with context_obj.summarizing() as ctx:
                if ctx is not None:
                    self.log.info("开始总结群 %d 消息", group_id)
                    await memory_system.extract_stored_group_message_advanced(
                        messages_str=messages_str,
                        bot_id=msg.event.self_id,
                        group_id=group_id,
                    )
        else:
            context_obj:PrivateContext
            async with context_obj.summarizing() as ctx:
                if ctx is not None:
                    self.log.info("开始总结私聊 %d 消息", context_obj.user_id)
                    msgs = [{"role": "user", "content": messages_str}]
                    await memory_system.extract_stored_message(
                        messages=msgs,
                        user_id=context_obj.user_id,
                    )

    async def groom_context_storage(self):
        """整理上下文存储：归档不活跃项目"""
        self.log.info("正在对上下文进行检测归档!")
        await self.lifecycle_manager.conduct_data_persistence(
            management_context_dict = self.group_dict,
            is_user_context = False
        )
        await self.lifecycle_manager.conduct_data_persistence(
            management_context_dict = self.private_dict
        )

    async def context_storage(self):
        """整理上下文存储：全部存储"""
        self.log.info("正在对上下文进行批量备份!")
        await self.lifecycle_manager.backup_data(
            management_context_dict = self.group_dict,
            is_user_context = False
        )
        await self.lifecycle_manager.backup_data(
            management_context_dict = self.private_dict
        )


    async def get_private_context(self, user_id: int) -> PrivateContext:
        """获取指定user的PrivateContext实例
        
        Args:
            user_id: 用户ID
            
        Returns:
            PrivateContext: 私聊上下文实例
        """
        if private_example := self.private_dict.get(user_id):
            private_example.update_time()
            return private_example
        else:
            
            messages = await self.lifecycle_manager.get_user_context(
                user_id
            )
            
            chat_context = Context(
                messages = messages if messages else [],
                user_max_record = self.private_max_record,
                play_role = self.play_role_list.get(
                    self.default_play_role, 
                    self.play_role_list["none"]
                )
            )
            
            private_example = self.private_dict[user_id] = \
            PrivateContext(
                user_id = user_id,
                chat_context = chat_context,
                play_roles = self.default_play_role,
                max_record = self.private_max_record,
            )
            return private_example
            

        
    async def get_group_context(self, group_id: int) -> GroupContext:
        """获取指定群的GroupContext实例
        
        Args:
            group_id: 群组ID
            
        Returns:
            GroupContext: 群组上下文实例
        """
        if group_example := self.group_dict.get(group_id):
            pass
        else:
            
            messages = await self.lifecycle_manager.get_group_context(
                group_id
            )
                        
            chat_context = Context(
                messages = messages if messages else [],
                user_max_record = self.LLM_max_record,
                play_role = self.play_role_list.get(
                    self.default_play_role, 
                    self.play_role_list["none"]
                )
            )
            
            group_example = self.group_dict[group_id] = \
            GroupContext(
                group_id=group_id,
                play_roles=self.default_play_role,
                chat_context=chat_context,
                group_max_record=self.group_max_record,
                initiative_chat = group_id in self.initiative_white_list,
                information_extraction = group_id in self.information_extraction
            )
        #因为这个群聊接收消息时会刷新时间，需要获取的时候更新时间了
        return group_example
        
        
    async def store_group_chat(self, group_id: str, context: Context) -> None:
        """存储指定群的LLM聊天上下文
        
        Args:
            group_id: 群组ID
            context: 要存储的上下文对象
        """
        (await self.get_group_context(group_id)).chat_context = context


    async def store_private_chat(self, user_id: int, context: Context) -> None:
        """存储指定用户的私聊聊天上下文
        
        Args:
            user_id: 用户ID
            context: 要存储的上下文对象
        """
        (await self.get_private_context(user_id)).chat_context = context
    
    async def get_group_messages_str(self, group_id: int) -> str:
        """返回群消息上下文(纯文本)"""
        return (await self.get_group_context(group_id)).build_context()

    async def add_group_messages_builder(
        self, 
        group_id: int, 
        builder: MessageBuilder,
        *,
        including_pictures: bool = False,
        including_audios: bool = False,
        including_videos: bool = False,
    ) -> MessageBuilder:
        """添加群消息，附带构造

        将群聊消息上下文转换为 MessageBuilder 多模态消息
        支持按类型控制保留的实际多媒体数量（不包括自己账号的多模态消息），超出数量的多模态项转为 CQ 码文本描述

        Args:
            group_id: 群组ID
            builder: 消息构建器
            including_pictures: True = 保留 DEFAULT_INCLUDING_PICTURES 条实际图片；
                                False = 使用 MediaProcessor 转为文本描述
            including_audios: True = 保留 DEFAULT_INCLUDING_AUDIOS 条实际音频；
                              False = 使用 MediaProcessor 转为文本描述
            including_videos: True = 保留 DEFAULT_INCLUDING_VIDEOS 条实际视频；
                              False = 使用 MediaProcessor 转为文本描述

        Returns:
            MessageBuilder: 构造完成的消息构建器
        """

        messages = list((await self.get_group_context(group_id)).messages)

        remaining_pictures = DEFAULT_INCLUDING_PICTURES if including_pictures else 0
        remaining_audios = DEFAULT_INCLUDING_AUDIOS if including_audios else 0
        remaining_videos = DEFAULT_INCLUDING_VIDEOS if including_videos else 0

        builder.add_text_left('</group_history>')

        for event in reversed(messages):
            
            # if not isinstance(event, MessageEvent):
            #     event:OneBotEvent
            #     builder.add_text_left(event.format_event_simple)
            #这段目前没什么用，感觉以后这个消息段不止会放消息

            if isinstance(event, MessageSentEvent):
                builder.add_text_left(event.llm_formatted_message)
                continue
            
            builder.add_text_left('\n</user_message>\n</MESSAGE>')

            for segment in reversed(event.segments):
                if isinstance(segment, TextSegment):
                    builder.add_text_left(segment.text)

                elif isinstance(segment, ImageSegment):
                    if remaining_pictures > 0:
                        if url := segment.url or segment.file.file:
                            try:
                                result = await url_to_image_jpeg(url, file_name=segment.file_name)
                                builder.add_image_base64_left(result.data, result.mime)
                            except Exception as e:
                                self.log.warning(f"图片转码失败 url={url}: {e}")
                            remaining_pictures -= 1
                        cq_text = (
                            f"[CQ:image,file={segment.file_name or 'unknown'}]"
                        )
                        builder.add_text_left(cq_text)
                    else:
                        if segment.text_description:
                            builder.add_text_left(f"[CQ:image,file={segment.file_name or 'unknown'},summary:{segment.text_description}]")
                        else:
                            builder.add_text_left(f"[CQ:image,file={segment.file_name or 'unknown'}]" )

                elif isinstance(segment, RecordSegment):
                    if remaining_audios > 0:
                        audio_url = segment.url or segment.file.file
                        try:
                            result = await url_to_audio_mp3(audio_url, segment.file_name)
                            builder.add_audio_left(result.data, result.fmt)
                            remaining_audios -= 1
                            cq_text = (
                                f"[CQ:record,file={segment.file_name or 'unknown'}]"
                            )
                            builder.add_text_left(cq_text)
                        except Exception as e:
                            self.log.warning(f"音频下载失败，降级文本识别 url={audio_url}: {e}")
                            if not segment.text_description:
                                try:
                                    desc = await self.media_processor.audio_to_text(audio_url)
                                    segment.text_description = desc
                                except Exception:
                                    segment.text_description = "<描述获取失败>"
                            builder.add_text_left(
                                f"[CQ:record,file={segment.file_name or 'unknown'},summary:{segment.text_description}]"
                            )
                    else:
                        if segment.text_description:
                            builder.add_text_left(f"[CQ:record,file={segment.file_name or 'unknown'},summary:{segment.text_description}]")
                        else:
                            builder.add_text_left(f"[CQ:record,file={segment.file_name or 'unknown'}]" )

                elif isinstance(segment, VideoSegment):
                    if remaining_videos > 0:
                        video_url = segment.url or segment.file.file
                        try:
                            result = await url_to_video_mp4(video_url, segment.file_name)
                            builder.add_video_base64_left(result.data, result.mime)
                        except Exception as e:
                            self.log.warning(f"视频转码失败 url={video_url}: {e}")
                        remaining_videos -= 1
                        cq_text = (
                            f"[CQ:video,file={segment.file_name or 'unknown'}]"
                        )
                        builder.add_text_left(cq_text)
                    else:
                        if segment.text_description:
                            builder.add_text_left(f"[CQ:video,file={segment.file_name or 'unknown'},summary:{segment.text_description}]")
                        else:
                            builder.add_text_left(f"[CQ:video,file={segment.file_name or 'unknown'}]" )

                else:
                    builder.add_text_left(segment.__str__())

            builder.add_text_left(
                f'<MESSAGE user_id={event.user_id}'
                f' nick_name={event.sender_nickname}'
                f' time={datetime.datetime.fromtimestamp(event.time).strftime('%Y-%m-%d %H:%M:%S')}>'
                f'\n<user_message>'
            )

        builder.add_text_left('<group_history>')

        return builder

    async def get_group_LLM_decision_parameters(self, group_id:int)->LLMGroupChatCondition:
        """返回LLM聊天决策参数对象"""
        return (await self.get_group_context(group_id)).LLM_chat_decision_parameters
    
    async def get_group_window_msg_count(self, group_id: int)->int:
        """返回一个群的近期消息数量统计

        Args:
            group_id (str): 指定群号

        Returns:
            int: 消息计数
        """
        return (await self.get_group_context(group_id)).time_window.get()
        
    async def add_message_record(
        self,
        msg: atriMessageEvent,
    ) -> tuple[str, GroupContext | PrivateContext] | None:
        """添加消息到群组/私聊上下文

        基于 atriMessageEvent 中的 OneBotEvent 类型判断路由：
        - 有 group_id → 群上下文 (GroupMessageEvent / GroupNoticeEvent / MessageSentEvent)
        - PrivateMessageEvent → 私聊上下文

        Args:
            msg: 新系统的消息事件对象

        Returns:
            需要总结时返回 (消息文本, 上下文对象)
        """
        if msg.group_id is not None:
            group_context = msg._extra["group_context"]

            if isinstance(msg.event, MessageSentEvent):
                group_context.LLM_chat_decision_parameters.time_window.add()

            return await group_context.add_group_chat_event(msg)

        elif isinstance(msg.event, PrivateMessageEvent):
            return await msg._extra['private_context'].add_private_chat_event(msg)

        return None
        
    
    async def reset_group_chat(self, group_id: int) -> None:
        """重置指定群的LLM聊天上下文
        
        Args:
            group_id: 群组ID
        """
        context =await self.get_group_context(group_id)
        async with context.async_lock:
            context.chat_context.clear()
            self.log.info(f"已重置群{group_id}的聊天上下文")
            

    async def reset_private_chat(self, user_id: int) -> None:
        """重置指定用户的LLM聊天上下文
        
        Args:
            user_id: 用户id及qq号
        """
        context =await self.get_private_context(user_id)
        async with context.async_lock:
            context.chat_context.clear()
            self.log.info(f"已重置user:{user_id}的聊天上下文")
    
    async def set_group_role(self, group_id: int, role_key: str) -> bool:
        """设置指定群的扮演角色
        
        Args:
            group_id: 群组ID
            role_key: 角色键名
            
        Returns:
            bool: 是否设置成功
        """
        group_context =await self.get_group_context(group_id)
        
        async with group_context.async_lock:
            if role_key in self.play_role_list:
                group_context.play_roles = role_key
                group_context.chat_context.play_role = self.play_role_list[role_key]
            else:
                raise ValueError("指定了不存在的角色键名!")
            
        await self.reset_group_chat(group_id)
        self.log.info(f"已设置群{group_id}的角色为: {role_key}")
        return

    async def set_private_role(self, user_id: int, role_key: str) -> bool:
        """设置指定私聊扮演角色
        
        Args:
            user_id: 用户ID
            role_key: 角色键名
            
        Returns:
            bool: 是否设置成功
        """
        group_context =await self.get_private_context(user_id)
        
        async with group_context.async_lock:
            if role_key in self.play_role_list:
                group_context.play_roles = role_key
                group_context.chat_context.play_role = self.play_role_list[role_key]
            else:
                raise ValueError("指定了不存在的角色键名!")
            
        await self.reset_private_chat(user_id)
        self.log.info(f"已设置user:{user_id}的聊天角色为: {role_key}")
        return
    
    async def get_group_role_str(self, group_id: int)->str:
        """获取指定群聊的聊天人设

        Args:
            group_id (int): 群组ID

        Returns:
            str: 人设文本
        """
        return (await self.get_group_context(group_id)).chat_context.play_role
    
    async def clear_group_role(self, group_id: int) -> None:
        """清除指定群的自定义角色，恢复为默认角色
        
        Args:
            group_id: 群组ID
        """
        group_context =await self.get_group_context(group_id)
        async with group_context.async_lock:
            
            group_context.play_roles = self.default_play_role
            group_context.chat_context.play_role = self.play_role_list.get(
                self.default_play_role, 
                self.play_role_list["none"]
            )
            await self.reset_group_chat(group_id)
            self.log.info(f"已清除群{group_id}的自定义角色，恢复为默认角色")
    
    
    def anew_character_settings(self) -> None:
        """重新加载角色设定"""
        self.play_role_list = {"none": ""}
        self._load_character_settings()
        
    
    def _load_character_settings(self) -> None:
        """加载角色设定文件"""
        import os
        
        if not os.path.exists(self.character_folder):
            self.log.warning(f"角色设定文件夹不存在: {self.character_folder}")
            return
        
        for character_setting in os.listdir(self.character_folder):
            if character_setting.endswith(".txt"):
                key = os.path.splitext(character_setting)[0]
                file_path = os.path.join(self.character_folder, character_setting)
                
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 40 * 1024:
                        self.log.warning(f"文件过大({file_size/1024:.1f}KB)，跳过: {character_setting}")
                        continue
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    self.play_role_list[key] = content
                    self.log.debug(f"已加载角色设定: {key}")
                    
                except Exception as e:
                    self.log.error(f"加载角色设定文件 '{character_setting}' 失败: {e}")
    
    