import asyncio
from logging import Logger

# from atribot.common import common
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI

from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_loader import command_loader
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from atribot.core.message_manage import message_router
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.network_connections.WebSocketClient import WebSocketClient
from atribot.core.network_connections.WebSocketServer import WebSocketServer
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.chat import GroupChat
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.LLM_supervisor import LLMCoordinator
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.LLMchat.memory.memiry_system import memorySystem
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.model_api.ai_connection_manager import AiConnectionManager
from atribot.LLMchat.model_api.bigModel_api import AsyncBigModelApi
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase
from atribot.LLMchat.skills.skills_manager import SkillsManager


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
        self.config = atriConfig()
        container.register("config",self.config)
        
        # 时间触发器,后面服务会依赖就只能放最前面了
        TriggerSupervisor = TimeTriggerSupervisor()
        container.register(
            "TimeTriggerSupervisor",
            TriggerSupervisor
        )
        
        #MCP
        mcp_server = FuncCall(self.config.file_path.mcp_config)
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
        
        #模型供应商
        LLMSupplier = AiConnectionManager()
        await LLMSupplier.initialize_connections(self.config.file_path.supplier_config_path)
        container.register(
            "LLMSupplier",
            LLMSupplier
        )
        bigModel = AsyncBigModelApi()
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
        
        #Skills的管理
        container.register(
            "SkillsManager",
            SkillsManager(skill_dir=self.config.file_path.agent_skills)
        )
        
        #ai使用的沙盒
        try:
            sand_box:SandBoxBase = DockerSandbox(
                config = self.config.sand_box
            )
            await sand_box.start()
            container.register(
                "SandBox",    
                sand_box
            )
        except Exception as e:
            self.logger.exception(f"LLM使用的使用的沙盒初始化失败{e}")
        
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
                initiative_white_list = self.config.group_initiative_chat_white_list,
                information_extraction = self.config.group_information_extraction,
            )
        )
        
        container.register(
            "EmojiCore",
            EmojiCore(folder_path = self.config.file_path.emoji)
        )

        #权限
        container.register(
            "PermissionsManagement",
            await PermissionsManagement.create()
        )
        
        #启动时间触发器的主循环
        await TriggerSupervisor.start()

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
        send_message = QQAPIClient(
            token = self.config.network.access_token, 
            http_base_url = self.config.network.url, 
            connection_type = self.config.network.connection_type
        )
        container.register("SendMessage",send_message)
        
        
        #指令
        container.register(
            "CommandSystem",
            CommandSystem()
        )
        CommandLoader = command_loader(self.config.file_path.commands)
        container.register("CommandLoader",CommandLoader)
        
        #处理模型响应
        container.register(
            "LLMsupervisor",
            LLMCoordinator()
        )
        
        #AIchat
        container.register(
            "GroupChat",
            GroupChat()
        )
