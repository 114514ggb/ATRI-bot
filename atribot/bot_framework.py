from atribot.core.command.async_permissions_management import permissions_management
from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.core.network_connections.WebSocketClient import WebSocketClient
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.LLMchat.LLMsupervisor import large_language_model_supervisor
from atribot.LLMchat.model_api.bigModel_api import async_bigModel_api
from atribot.core.cache.message_buffer_memory import message_cache
from atribot.core.command.command_parsing import command_system
from atribot.core.cache.chan_context import context_management
from atribot.core.command.command_loader import command_loader
from atribot.core.db.atri_async_Database import AtriDB_Async
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.core.message_manage import message_router
from atribot.core.service_container import container
from atribot.LLMchat.emoji_system import emoji_core
from atribot.core.atri_config import atri_config
from atribot.LLMchat.chat import group_chat
# from atribot.common import common
from logging import Logger


from fastapi import FastAPI, WebSocket
from typing import Dict, Any
import uvicorn
import asyncio




class BotFramework:
    
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
            await AtriDB_Async.create(
                self.config.mysql.host, 
                self.config.mysql.user,
                self.config.mysql.password
            )
        )
        
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
            model_list = {
                "GLM-4.5-Flash": {
                "visual_sense": False
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
        
        #常用
        # container.register(
        #     "Common",
        #     common()
        # )
        
        #缓存
        container.register(
            "MessageCache",
            message_cache(
                self.config.ai_chat.group_max_record,
                self.config.ai_chat.private_max_record
            )
        )
        container.register(
            "ChatContext",
            context_management(
                self.config.ai_chat.playRole,
                self.config.ai_chat.ai_max_record,
                self.config.file_path.chat_manager
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
        
        self.logger.critical("bot作为服务端的连接模块写完后没有测试过最好使用bot_client!")
        
        _message_router = message_router()
        app = FastAPI()
        
        if server_type == "http":
            
            @app.post("/")
            async def handle_http_event(data: Dict[str, Any]):
                """处理HTTP事件"""
                asyncio.create_task(_message_router.main(data))
                return {"status": "OK", "code": 200}
            
        else:
            self.logger.critical("这个WebSocket_server应该更是完全不能工作!")
            @app.websocket("/ws")
            async def websocket_endpoint(websocket: WebSocket):
                """WebSocket连接（服务端模式）"""
                token = websocket.query_params.get("access_token")
                if token != self.config.network.access_token:
                    await websocket.close(code=1008)  # 1008 表示权限错误
                    return
                
                await websocket.accept()
                try:
                    while True:
                        data = await websocket.receive_json()
                        await _message_router.main(data)
                        await websocket.send_json({"status": "processed"})
                except Exception as e:
                    self.logger.error(f"WebSocket error: {e}")
                finally:
                    await websocket.close()
        
        
        self.creation_send_message()
        
        uvicorn_app = uvicorn.Config(
            app, 
            host="localhost", 
            port=self.config.network.Server_port,
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
            "WebSocketClient",
            WSClient
        )
        
        self.creation_send_message()
        _message_router = message_router()
        
        await WSClient.connect()

        WSClient.add_listener(_message_router.main)
        
        await WSClient.start_while()
    
    def creation_send_message(self)->None:
        """初始化发送消息class,还有环节最后的加载"""
        send_message = qq_send_message(
            self.config.network.access_token, 
            self.config.network.url, 
            self.config.network.connection_type,
            self.config.file_path.document
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
