import re
from enum import Enum
from logging import Logger
from typing import Callable, Dict, List, Optional, Tuple

from atribot.core.db.async_db_basics import AsyncDatabaseBase
from atribot.core.event_trigger.string_respond import string_response
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage


class EventType(Enum):
    """事件类型枚举。"""
    META = 'meta_event'
    """元事件"""
    REQUEST = 'request'
    """请求事件"""
    NOTICE = 'notice'
    """通知事件"""
    MESSAGE = 'message'
    """消息事件"""
    MESSAGE_SENT = 'message_sent'
    """消息发送事件"""


class EventTrigger:
    """事件分类触发器(用于处理非主聊天等效果的之外的消息分发处理)

    该类用于根据事件类型 (post_type) 将事件分发给对应的处理函数
    支持通过装饰器的方式注册特定条件下的事件处理器，如果返回一个真值就不会继续传递这个消息了

    用法示例:
        trigger = EventTrigger()

        @trigger.on_notice(lambda data: data.get('sub_type') == 'poke')
        async def my_poke_handler(message:ChatMessage, data: dict) -> bool::
            pass

        # 无条件响应所有消息
        @trigger.on_message()
        async def my_message_handler(message:ChatMessage, data: dict) -> bool:
            pass
    """

    def __init__(self):
        """初始化 EventTrigger 实例，并注册默认的事件处理器"""
        self.log: Logger = container.get_by_type(Logger).getChild("Event")
        self.send_message:QQAPIClient = container.get("SendMessage")
        self.str_response = string_response()

        self._processors: Dict[EventType, List[Tuple[Callable, Callable]]] = {
            EventType.META: [],
            EventType.REQUEST: [],
            EventType.NOTICE: [],
            EventType.MESSAGE: [],
            EventType.MESSAGE_SENT: [],
        }

        self.on_message()(self.str_response.manage)
        self.on_notice(
            lambda data: data.get('sub_type') in ["approve", 'kick', 'leave']
        )(self.manage_group_inform)
        self.on_request(
            lambda data: data.get('sub_type') == "add"
        )(self.manage_add_group)

    def on(self, event_type: EventType, condition: Optional[Callable] = None) -> Callable:
        """注册事件处理钩子的通用装饰器工厂

        Args:
            event_type (EventType): 需要监听的事件类型枚举
            condition (Optional[Callable], optional): 过滤条件函数。接收原始 data 字典作为参数，
                返回 bool 值。如果为 None,则无条件响应所有该类型的事件。默认为 None。

        Returns:
            Callable: 装饰器函数。被装饰的函数签名应为 `async def handler(message:ChatMessage, data: dict) -> bool:`
            如果函数返回一个真值就不会继续传递这个消息了
        """
        def decorator(func: Callable) -> Callable:
            self._processors[event_type].append((condition if condition is not None else (lambda _: True), func))
            return func

        return decorator

    def on_meta(self, condition: Optional[Callable] = None) -> Callable:
        """注册元事件 (meta_event) 钩子

        Args:
            condition (Optional[Callable], optional): 过滤条件函数。默认为 None

        Returns:
            Callable: 装饰器函数
        """
        return self.on(EventType.META, condition)

    def on_request(self, condition: Optional[Callable] = None) -> Callable:
        """注册请求事件 (request) 钩子

        Args:
            condition (Optional[Callable], optional): 过滤条件函数。默认为 None。

        Returns:
            Callable: 装饰器函数
        """
        return self.on(EventType.REQUEST, condition)

    def on_notice(self, condition: Optional[Callable] = None) -> Callable:
        """注册通知事件 (notice) 钩子

        Args:
            condition (Optional[Callable], optional): 过滤条件函数。默认为 None。

        Returns:
            Callable: 装饰器函数
        """
        return self.on(EventType.NOTICE, condition)

    def on_message(self, condition: Optional[Callable] = None) -> Callable:
        """注册消息事件 (message) 钩子

        Args:
            condition (Optional[Callable], optional): 过滤条件函数。默认为 None。

        Returns:
            Callable: 装饰器函数
        """
        return self.on(EventType.MESSAGE, condition)

    def on_message_sent(self, condition: Optional[Callable] = None) -> Callable:
        """注册自身消息发送事件 (message_sent) 钩子

        Args:
            condition (Optional[Callable], optional): 过滤条件函数。默认为 None。

        Returns:
            Callable: 装饰器函数
        """
        return self.on(EventType.MESSAGE_SENT, condition)

    async def dispatch(self, message:ChatMessage, data:dict) -> None:
        """将事件分发到所有满足条件的处理器"""
        # if message.group_id in [936819059]:
        #     return

        post_type = data.get('post_type')
        try:
            event_type = EventType(post_type)
        except ValueError:
            self.log.debug(f"收到未知的事件类型: {post_type}")
            return

        for condition, handler in self._processors.get(event_type, []):
            if condition(data):
                try:
                    if await handler(message, data):
                        break
                except Exception as e:
                    self.log.exception(f"处理器执行失败: {handler.__name__}, 错误: {e}")

    async def manage_group_inform(self, message:ChatMessage, data: dict) -> bool:
        """管理群通知事件"""

        sub_type = data['sub_type']
        user_id = message.user_id
        group_id = message.group_id
        
        if sub_type == "approve":
            await self.send_message.send_group_msg(group_id, f"欢迎[CQ:at,qq={user_id}]加入群聊！")
            DatabaseBase: AsyncDatabaseBase = container.get("database")
            await DatabaseBase.add_user(
                user_id=user_id,
                nickname="NOT_SET"  # 以后发消息时会更新
            )
        elif sub_type == 'kick':
            await self.send_message.send_group_msg(group_id, f"[CQ:at,qq={user_id}]({user_id})被[CQ:at,qq={data['operator_id']}]请出群聊！")
        elif sub_type == 'leave':
            await self.send_message.send_group_msg(group_id, f"[CQ:at,qq={user_id}]({user_id})永久的离开了我们！希望以后安好~")
        return True
            
    async def manage_add_group(self, message:ChatMessage, data: dict) -> bool:
        """管理加群的请求"""
        white_list_group:dict = {
            1038698883 : [
                r"ATRI",
            ],
            2169027872 : [
                r"亚托莉|吖密|ATRI|b站",
            ]
        }
        """白名单群key:群号 value:验证的正则表达式"""
            
        group_id = message.group_id
        comment = data.get('comment', '')

        if match := re.search(r"学习|交流|谢谢|同意|趣味相投|小白", comment):
            await self.send_message.set_group_add_request(data['flag'], False)
            await self.send_message.send_group_msg(
                group_id,
                f"已自动拒绝可疑加群请求！匹配到关键词：{match.group()}\n验证信息:\n{comment}"
            )
            return True

        if group_id in white_list_group:
            if answer_match := re.search(r"答案：\s*(.*)", comment):
                answer = answer_match.group(1).strip()
                for pattern in white_list_group[group_id]:
                    if re.search(pattern, answer, re.IGNORECASE):
                        await self.send_message.set_group_add_request(data['flag'], True)
                        return True
                    
            if qq_level := (await self.send_message.get_stranger_info(message.user_id)).get("qqLevel",0):
                if qq_level < 10:
                    await self.send_message.set_group_add_request(data['flag'], False)
                    await self.send_message.send_group_msg(
                        group_id,
                        f"已自动拒绝可疑加群请求！等级过低:{qq_level}级\n验证信息:\n{comment or "None"}"
                    )
                    return True

        await self.send_message.send_group_msg(
            group_id, f"有人申请加群了!\n[CQ:at,qq={message.user_id}]({message.user_id})\n{comment}"
        )
        return True        

    