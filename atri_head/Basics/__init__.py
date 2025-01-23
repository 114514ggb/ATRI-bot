from .AI_interaction import AI_interaction
from .chance import Chance
from .qq_send_message import QQ_send_message
from .command import Command #还有一个Permissions_management继承在里面

__all__ = ["Basics"]

class Basics:
    """基础功能类"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Basics, cls).__new__(cls)
        return cls._instance

    def __init__(self, http_base_url  = "http://localhost:8088", token = "ATRI114514", playRole = "ATRI",connection_type = None):

        if not hasattr(self, "_initialized"):
            self.QQ_send_message = QQ_send_message(token, http_base_url, connection_type) #QQ 发送消息等交互
            self.AI_interaction = AI_interaction(playRole) #AI 交互
            self.Command = Command() #命令还有权限管理
            self.Chance = Chance() #随机事件
            self._initialized = True  # 标记为已初始化 
