import time

from atribot.core.type.chat_message_types import ChatMessage


class Message:
    """消息基础类，表示系统中的一个消息单元

    注：目前没有使用,或许在计划中后面这个有用
        对消息产生和接收到差值太多的消息只进行存储处理，不进行响应
        对处理过久的消息进行丢弃
    """

    create_time: float
    """消息产生时间"""
    receive_time: float
    """消息处理器首次接收到这次消息的时间"""
    process_time: float
    """到达当前处理节点的时间"""
    rich_data: ChatMessage
    """具体的处理数据"""

    def __init__(self, rich_data: ChatMessage):
        self.create_time = rich_data.time
        self.receive_time = self.process_time = time.time()
        self.rich_data: ChatMessage = rich_data

    def update_process_time(self) -> None:
        """更新当前处理节点时间为当前时间戳"""
        self.process_time = time.time()