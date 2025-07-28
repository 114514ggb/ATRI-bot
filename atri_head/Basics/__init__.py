from .AI_interaction import AI_interaction
# from .atri_Database import AtriDB #数据库
from .message_buffer_memory import MessageCache
from .atri_async_Database import AtriDB_Async
from .chance import Chance
from .qq_send_message import QQ_send_message
from .command import Command #还有一个Permissions_management继承在里面
from .chan_context import ai_chat_manager
from .Command_information import Command as Command_information
from .exit_save import graceful_exiter
from .mcp_tool_manager import FuncCall
from .atri_config import atri_config
from .AI_connection_manager import AI_connection_manager
from threading import Lock
import asyncio

__all__ = ["Basics","Command_information","Command","Chance"]

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
 
    def __init__(self):

        if not hasattr(self, "_initialized"):
            self.config = atri_config()
            """配置参数"""
            self.QQ_send_message = QQ_send_message(
                self.config.network.access_token, 
                self.config.network.url, 
                self.config.network.connection_type
            ) 
            """QQ 发送消息等交互"""
            self.AI_interaction = AI_interaction() 
            """AI功能类"""
            self.exiter_save = graceful_exiter()
            """退出保存"""
            self.AI_supplier_manager = AI_connection_manager(
                self.config.file_path.supplier_config_path
            )
            """ai的api供应商管理"""
            self.MessageCache = MessageCache(
                self.config.ai_chat.group_max_record,
                self.config.ai_chat.private_max_record
            )
            """消息暂时缓存"""
            self.ai_chat_manager = ai_chat_manager(
                self.config.ai_chat.playRole,
                self.config.ai_chat.ai_max_record,
                self.config.file_path.chat_manager
            )
            """ai上下文管理"""
            self.mcp_tool = FuncCall("atri_head/ai_chat/MCP/")
            """MCP工具类"""
            # self.database = AtriDB("localhost", "root", "180710") #数据库            
            
            self.async_database = None #异步数据库
            self._initialized = True  # 标记为已初始化 

    async def link_async_database(self) -> AtriDB_Async:
        """异步连接数据库"""
        async with self._async_init_lock:
            if self.async_database is None:
                self.async_database = await AtriDB_Async.create(
                    self.config.mysql.host, 
                    self.config.mysql.user,
                    self.config.mysql.password
                )
        return self.async_database