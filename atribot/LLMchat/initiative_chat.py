from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.types import GroupContext, LLMGroupChatCondition, RichData
from atribot.core.service_container import container
from atribot.LLMchat.chat import group_chat
from typing import List,Optional
from logging import Logger




class initiativeChat:
    """决定bot如何在合适的时机加入聊天"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.chat_manager:ChatManager = container.get("ChatManager")
        self.group_chet:group_chat = container.get("GroupChat")
        self.keyword_trigger_list = ["ATRI","哈基莉"]
        
    async def decision(self, message:RichData, at:bool = None)->bool:
        """决策是否应该发言"""
        data = message.primeval
        group_id = data["group_id"]
        
        if at:
            #被@了就一定要回复
            await self.group_chet.step_json(
                message = message,
                group_id = group_id,
                user_id= data["user_id"],
                prompt= "你现在被@到了，最好回复一下别人，除非你觉得对方很讨厌或是发送了过多的消息,可以选择不回复"
            )
            await self.chat_manager.get_group_context(group_id).LLM_chat_decision_parameters.reset_turns_since_last_llm()
            return True
        
        group_context = self.chat_manager.get_group_context(group_id)
        
        if await self.get_bot_active_reference(group_context) < 0.8: 
            #不能太吵,消息占比不是太高的时候才会考虑
            
            user_id:int = data["user_id"]
            decision_parameters: LLMGroupChatCondition = group_context.LLM_chat_decision_parameters
            
            if value := self.find_first_match(
                text = message.pure_text,
                patterns = self.keyword_trigger_list
            ):
                #关键词触发
                await self.group_chet.step_json(
                    message = message,
                    group_id = group_id,
                    user_id= user_id,
                    prompt= f"现在群里触发了关键词:{value},你该考虑一下是否回复他的消息了"
                )
                await decision_parameters.reset_turns_since_last_llm()
                return True
            
            
            if user_id == decision_parameters.last_trigger_user_id and decision_parameters.get_seconds_since_user_time()< 10:
                #考虑到追问的情况
                await self.group_chet.step_json(
                    message = message,
                    group_id = group_id,
                    user_id= user_id,
                    prompt= "尝试考虑用户在你回复后，是否下一句是想接着聊天的情况,你应观察是否应该进行回复."
                )
                await decision_parameters.reset_turns_since_last_llm()
                return True
            
            #"现在你的消息被引用，你需要好好想想要不要回复或是怎么回复"暂时不做
            
            #最后要是都没触发就是决定根据概率来触发了
            if await self.roll_trigger_probability(group_context,decision_parameters):
                await self.group_chet.step_json(
                    message = message,
                    group_id = group_id,
                    user_id= user_id,
                    prompt= "你现在要做的是观察上下文,简单判断一下群里情况,看看群里聊的是不是你感兴趣的.如果感兴趣可以尝试回复."
                    "推荐在群里当卖萌充当吉祥物。如果有一些事你可以表示一些看法，或是赞同别人的话，或是夸别人还有和群友一起复读一些话，回答一些你自己认为能完美解决的问题,不要在话中带上或问有什么需要帮忙,如果你看不懂建议就别回复了"
                )
                await decision_parameters.reset_turns_since_last_llm()
                return True
        
        await decision_parameters.add_turns_since_last_llm()
           
        return False
    
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
        根据一些条件决定是否以一定概率触发聊天
        """
        if (
            decision_parameters.turns_since_last_llm > 15 
            and await group_context.time_window.get() > 2
            and decision_parameters.get_seconds_since_llm_time() > 30
            and decision_parameters.get_seconds_since_user_time() > 60
            # and (await self.get_bot_active_reference(group_context)) < 0.6
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