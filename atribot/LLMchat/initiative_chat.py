from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.types import GroupContext, LLMGroupChatCondition, RichData
from atribot.core.service_container import container
from atribot.LLMchat.chat import group_chat
from typing import List, Literal,Optional
from logging import Logger




class initiativeChat:
    """决定bot如何在合适的时机加入聊天"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.chat_manager:ChatManager = container.get("ChatManager")
        self.group_chat:group_chat = container.get("GroupChat")
        self.keyword_trigger_list = ["亚托莉","哈基莉"]
    
    async def decision(self, message: RichData, at: bool = False) -> bool:
        """决策是否应该发言"""
        data = message.primeval
        if not data.get("message"):
            return False

        group_id = data["group_id"]
        user_id: int = data["user_id"]
        group_context = self.chat_manager.get_group_context(group_id)
        params: LLMGroupChatCondition = group_context.LLM_chat_decision_parameters

        #被@检测
        if at:
            decision =  await self._execute_reply(
                message, group_id, params,
                log_msg=f"Bot was @ed by user {user_id}, preparing to respond.",
                prompt="你现在被@到了，最好回复一下别人，除非你觉得不感兴趣或是你发送了过多的消息，面对多次重复输入,就选择静默不回复"
            )
            await group_context.LLM_chat_decision_parameters.update_trigger_user(user_id)
            return decision

        #关键词触发检测
        if value := self.find_first_match(message.pure_text, self.keyword_trigger_list):
            return await self._execute_reply(
                message, group_id, params,
                log_msg=f"Keyword '{value}' triggered by user {user_id}, preparing to respond.",
                prompt=f"现在群里触发了关键词:{value},你该考虑一下是否回复他的消息了,无关就保持沉默"
            )

        #活跃度限制而且消息要由文本部分
        if await self.get_bot_active_reference(group_context, 3) < 0.5 and message.pure_text.strip():
            
            #追问检测
            if params.get_seconds_since_user_time() < 10 and user_id == params.last_trigger_user_id:
                decision = await self._execute_reply(
                    message, group_id, params,
                    log_msg=f"User {user_id} follow-up detected, preparing to respond.",
                    prompt="尝试考虑用户在你回复后，是否下一句是想接着聊天的情况,你应观察是否应该进行回复,确定是接你的话就进行回复，不然就保持沉默"
                )
                await group_context.LLM_chat_decision_parameters.update_trigger_user(user_id)
                return decision
            
            #"现在你的消息被引用，你需要好好想想要不要回复或是怎么回复"暂时不做
            
            if await self.roll_trigger_probability(group_context, params):
                return await self._execute_reply(
                    message, group_id, params,
                    log_msg="Random trigger activated, preparing to respond.",
                    prompt="你现在要做的是观察上下文,简单判断一下群里情况,看看群里聊的是不是你感兴趣的.如果感兴趣可以尝试回复.但是不要提出问题，不知道就建议保持沉默.如果传入了图像是当前群里发送最新一条消息的所带或最新消息引用消息里的图像，并不是专门发送给你的,不要弄错了"
                    "推荐在群里当卖萌充当吉祥物。如果有一些事你可以表示一些看法，或是赞同别人的话，或是夸别人还有和群友一起复读一些话，回答一些你自己认为能完美解决的问题,不要打断或打扰到别人的聊天,不要在话中带上或问有什么需要帮忙,如果你看不懂建议就保持静默,不要频繁发言，尽量保持低调"
                )

        await params.add_turns_since_last_llm()
        return False
    
    
    async def _execute_reply(
        self, 
        message: RichData, 
        group_id:int,  
        decision_params:LLMGroupChatCondition,
        log_msg:str, 
        prompt:str
    ) -> Literal[True]:
            """回复执行逻辑"""
            self.logger.info(f"Group {group_id} {log_msg}")
            await decision_params.reset_turns_since_last_llm() 
            
            await self.group_chat.step_json(
                message=message,
                group_id=group_id,
                prompt=prompt
            )
            return True
    
    @staticmethod
    def find_first_match(text: str, patterns: List[str]) -> Optional[str]:
        """
        在 text 中查找是否包含 patterns 中的任意一个子串。
        找到第一个匹配的子串后立即返回该子串，否则返回 None。
        
        参数:
            text (str): 要搜索的字符串
            patterns (List[str]): 要匹配的子串列表
        
        返回:
            Optional[str]: 第一个匹配的子串，或 None
        """
        for pattern in patterns:
            if pattern in text:
                return pattern
        return None
    
    async def roll_trigger_probability(self, group_context:GroupContext, decision_parameters:LLMGroupChatCondition) -> bool:
        """
        根据一些条件决定是否触发聊天
        """
        if (
            decision_parameters.turns_since_last_llm > 30 
            and await group_context.time_window.get() >= 2
            and decision_parameters.get_seconds_since_user_time() > 300
            and decision_parameters.get_seconds_since_llm_time() > 120
        ):
            return True
        
        return False
    
    
    async def get_bot_active_reference(self, group_context:GroupContext, bayesian_smoothing_correction:int = 1)->float:
        """获取指定群聊的人机消息占比的参考值

        Args:
            group_context (GroupContext): 群组上下文
            bayesian_smoothing_correction (int): 贝叶斯平滑修正值

        Returns:
            float: 在窗口时间内的bot消息和群总消息的大约比值
        """
        if total_msgs := await group_context.time_window.get():
            if bot_msgs := await group_context.LLM_chat_decision_parameters.time_window.get():
                return bot_msgs / (total_msgs + bayesian_smoothing_correction)
        
        return 0.0