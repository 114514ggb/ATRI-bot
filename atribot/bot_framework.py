from atribot.core.command.async_permissions_management import permissions_management
from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.core.network_connections.WebSocketClient import WebSocketClient
from atribot.core.network_connections.WebSocketServer import WebSocketServer
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.LLMchat.LLMsupervisor import large_language_model_supervisor
from atribot.LLMchat.model_api.bigModel_api import async_bigModel_api
from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.command.command_parsing import command_system
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.core.command.command_loader import command_loader
from atribot.LLMchat.memory.memiry_system import memorySystem
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.core.message_manage import message_router
from atribot.core.service_container import container
from atribot.LLMchat.emoji_system import emoji_core
from atribot.core.atri_config import atri_config
from atribot.LLMchat.chat import group_chat
# from atribot.common import common
from typing import Dict, Any
from fastapi import FastAPI
from logging import Logger
import uvicorn
import asyncio




class BotFramework:
    """主初始化类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
    
    @classmethod
    async def create(cls):
        """工厂方法，替代 __ainit__"""
        self = cls()
        await self.initialize()
        return self
    
    async def initialize(self):
        """初始化"""
        #配置参数
        self.config = atri_config()
        container.register("config",self.config)
        
        #MCP
        mcp_server = FuncCall("atribot/LLMchat/MCP/")
        asyncio.create_task(mcp_server.mcp_service_selector())#放到后台不等待
        mcp_server.mcp_service_queue.put_nowait({"type": "init"})#初始化
        container.register(
            "MCP",
            mcp_server
        )
        
        #数据库
        container.register(
            "database",
            await atriAsyncPostgreSQL.create(
                host = self.config.database.host, 
                user = self.config.database.user,
                port = self.config.database.port,
                password = self.config.database.password
            )
        )
        
        #时间触发器
        TriggerSupervisor = TimeTriggerSupervisor()
        container.register(
            "TimeTriggerSupervisor",
            TriggerSupervisor
        )
        asyncio.create_task(TriggerSupervisor.start())
        
        #模型供应商
        LLMSupplier = ai_connection_manager()
        await LLMSupplier.initialize_connections(self.config.file_path.supplier_config_path)
        container.register(
            "LLMSupplier",
            LLMSupplier
        )
        bigModel = async_bigModel_api()
        await bigModel.initialize()
        LLMSupplier.add_connection(
            name = "bigModel",
            connection_object = bigModel,
            model_dict = {
                "GLM-4.5-Flash": {
                    "visual_sense": False
                },
                "GLM-4.6V-Flash": {
                    "visual_sense": True
                },
                "GLM-4V-Flash": {
                    "visual_sense": True
                },
                "GLM-4.1V-Thinking-Flash": {
                    "visual_sense": True
                },
                "GLM-Z1-Flash": {
                    "visual_sense": False
                }
            }
        )
        
        #向量数据库实现的记忆系统
        container.register(
            "memirySystem",    
            memorySystem()
        )
        
        #用户信息系统
        container.register(
            "UserSystem",    
            UserSystem()
        )
        
        #常用
        # container.register(
        #     "Common",
        #     common()
        # )
        
        #群类管理什么的
        container.register(
            "ChatManager",
            ChatManager(
                default_play_role = self.config.ai_chat.playRole,
                group_messages_max_limit = self.config.ai_chat.group_max_record,
                private_messages_max_limit = self.config.ai_chat.private_max_record,
                group_LLM_max_limit = self.config.ai_chat.ai_max_record,
                character_folder = self.config.file_path.chat_manager,
                initiative_white_list = self.config.group_initiative_chat_white_list
            )
        )
        
        container.register(
            "EmojiCore",
            emoji_core(
                folder_path = self.config.file_path.emoji,
                item_path = self.config.file_path.item_path
            )
        )

        #权限
        container.register(
            "PermissionsManagement",
            await permissions_management.create()
        )

        #连接配置
        server_type:str = self.config.network.connection_type
        if server_type in ["http", "WebSocket_server"]:
            await self.bot_side(server_type)
        elif server_type == "WebSocket_client":
            await self.bot_client()
        else:
            raise ValueError(f"不支持的连接类型: {server_type}")
        
        
    async def bot_side(self, server_type:str)->None:
        """bot作为服务端的时候连接

        Args:
            type (str): 连接类型
        """
        if server_type == "WebSocket_server":
            WSServer = WebSocketServer(
                    host = self.config.network.host, 
                    port = self.config.network.server_port,
                    access_token = self.config.network.access_token, 
            )
            
            container.register(
                "WebSocket",
                WSServer
            )
            
            self.creation_send_message()
            
            WSServer.add_listener(message_router().main)
        
            await WSServer.start()
            
            await WSServer.wait_for_connection()
            return
        
        
        self.creation_send_message()
        _message_router = message_router()
        
        app = FastAPI() 
        
        @app.post("/")
        async def handle_http_event(data: Dict[str, Any]):
            """处理HTTP事件"""
            asyncio.create_task(_message_router.main(data))
            return {"status": "OK", "code": 200}
                
        uvicorn_app = uvicorn.Config(
            app, 
            host="localhost", 
            port=self.config.network.server_port,
            workers=8 #进程数
        )
        
        server = uvicorn.Server(uvicorn_app)
        await server.serve()
        
    async def bot_client(self)->None:
        """bot作为客户端"""
        WSClient = WebSocketClient(
            url=self.config.network.url, 
            access_token=self.config.network.access_token
        )
        
        container.register(
            "WebSocket",
            WSClient
        )
        
        self.creation_send_message()

        WSClient.add_listener(message_router().main)
        
        await WSClient.start()
    
    def creation_send_message(self)->None:
        """初始化发送消息class,还有环节最后的加载"""
        send_message = qq_send_message(
            token = self.config.network.access_token, 
            http_base_url = self.config.network.url, 
            connection_type = self.config.network.connection_type,
            File_root_directory = self.config.file_path.document
        )
        container.register("SendMessage",send_message)
        
        
        #指令
        container.register(
            "CommandSystem",
            command_system()
        )
        CommandLoader = command_loader()
        CommandLoader.load_commands_from_directory(self.config.file_path.commands)
        container.register("CommandLoader",CommandLoader)
        
        #处理模型响应
        container.register(
            "LLMsupervisor",
            large_language_model_supervisor()
        )
        
        #AIchat
        container.register(
            "GroupChat",
            group_chat()
        )
