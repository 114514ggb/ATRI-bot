from .AI_interaction import AI_interaction
# from .atri_Database import AtriDB #数据库
from .atri_async_Database import AtriDB_Async
from .chance import Chance
from .qq_send_message import QQ_send_message
from .command import Command #还有一个Permissions_management继承在里面
from .Command_information import Command as Command_information
from threading import Lock
import asyncio

__all__ = ["Basics","Command_information"]

class Basics:
    """基础功能类"""
    _instance = None
    _thread_lock = Lock()  # 线程级锁
    _async_init_lock = asyncio.Lock()  # 协程级锁

    def __new__(cls, *args, **kwargs):
        with cls._thread_lock:
            if cls._instance is None:
                cls._instance = super(Basics, cls).__new__(cls)
        return cls._instance

    def __init__(self, http_base_url  = "http://localhost:8088", token = "ATRI114514", playRole = "ATRI",connection_type = None):

        if not hasattr(self, "_initialized"):
            self.QQ_send_message = QQ_send_message(token, http_base_url, connection_type) #QQ 发送消息等交互
            self.AI_interaction = AI_interaction(playRole) #AI 交互
            self.Command = Command() #命令还有权限管理
            self.Chance = Chance() #随机事件
            # self.database = AtriDB("localhost", "root", "180710") #数据库
            self.async_database = None #异步数据库
            self._initialized = True  # 标记为已初始化 

    async def link_async_database(self, host:str, user:str, password:str) -> AtriDB_Async:
        """异步连接数据库"""
        async with self._async_init_lock:
            if self.async_database is None:
                self.async_database = await AtriDB_Async.create(host, user, password)
        return self.async_database