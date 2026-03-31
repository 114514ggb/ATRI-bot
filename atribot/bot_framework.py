import asyncio
from logging import Logger
from typing import Any, Awaitable, Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atribot.common_utils.http_client import HTTPClient
from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_loader import command_loader
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.event_trigger.event_trigger import EventTrigger
from atribot.core.message_manage import message_router
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.network_connections.WebSocketClient import WebSocketClient
from atribot.core.network_connections.WebSocketServer import WebSocketServer
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.chat import AgentChat, GroupChat, PrivateChat
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.LLM_supervisor import LLMCoordinator
from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.LLMchat.MCP.model_tools import tool_calls
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.memory.memory_system import memorySystem
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase
from atribot.LLMchat.skills.skills_manager import SkillsManager


class BotFramework:
    """主初始化类"""
    
    def __init__(self):
        self.logger: Logger = container.get("log")
        self._background_tasks: set[asyncio.Task[Any]] = set()
        """退出时统一回收的后台任务"""
        self._shutdown_task: asyncio.Task[None] | None = None
        self._is_shutdown = False
        """标记是否已经完成关闭"""
    
    @classmethod
    async def create(cls):
        """工厂初始化方法"""
        self = cls()
        try:
            await self.initialize()
        except BaseException:
            await self.graceful_shutdown()
            raise
        return self
    
    async def initialize(self):
        """初始化"""
        #配置参数
        self.config = atriConfig()
        container.register("config",self.config)

        #统一HTTP客户端
        http_client = HTTPClient()
        container.register("HTTPClient", http_client, cleanup=http_client.close)

        # 时间触发器,后面服务会依赖就只能放最前面了
        TriggerSupervisor = TimeTriggerSupervisor()
        container.register(
            "TimeTriggerSupervisor",
            TriggerSupervisor,
            cleanup=TriggerSupervisor.stop
        )
        
        #MCP
        mcp_server = FuncCall(self.config.file_path.mcp_config)
        mcp_server.load_presets_from_config(self.config.tool_presets)#加载工具列表配置
        self.create_background_task(mcp_server.mcp_service_selector())#放到后台不等待
        mcp_server.mcp_service_queue.put_nowait({"type": "init"})#初始化
        container.register(
            "MCP",
            mcp_server,
            cleanup=mcp_server.terminate
        )
        
        #数据库
        database = await AsyncPostgreSQL.create(
            host = self.config.database.host, 
            user = self.config.database.user,
            port = self.config.database.port,
            password = self.config.database.password
        )
        container.register(
            "database",
            database,
            cleanup=database.close_pool
        )
        
        #模型供应商
        LLMSupplier = LLMConnectionManager()
        await LLMSupplier.initialize_connections(self.config.file_path.supplier_config_path)
        container.register(
            "LLMSupplier",
            LLMSupplier,
            cleanup=LLMSupplier.close
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
                sand_box,
                cleanup=sand_box.stop
            )
        except Exception as e:
            self.logger.exception(f"LLM使用的使用的沙盒初始化失败{e}")
        
        #向量数据库实现的记忆系统
        container.register(
            "memorySystem",    
            memorySystem()
        )
        
        #用户信息系统
        container.register(
            "UserSystem",    
            UserSystem()
        )
        
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

        server_type: str = self.config.network.connection_type
        if server_type == "WebSocket_server":
            ws = WebSocketServer(
                host=self.config.network.host,
                port=self.config.network.server_port,
                access_token=self.config.network.access_token,
            )
            container.register("WebSocket", ws, cleanup=ws.close)
        elif server_type == "WebSocket_client":
            ws = WebSocketClient(
                url=self.config.network.url,
                access_token=self.config.network.access_token,
            )
            container.register("WebSocket", ws, cleanup=ws.close)
        elif server_type != "http":
            raise ValueError(f"不支持的连接类型: {server_type}")

        self._init_messaging_services()

        #管理面板
        self.create_background_task(self._start_admin_panel())

        await self._start_network(server_type)

    def _init_messaging_services(self) -> None:
        """发送消息以及相关的依赖"""
        container.register(
            "SendMessage", 
            QQAPIClient(
            token=self.config.network.access_token,
            http_base_url=self.config.network.url,
            connection_type=self.config.network.connection_type,)
        )

        #消息分发处理
        container.register("EventTrigger", EventTrigger())

        #指令
        container.register("CommandSystem", CommandSystem())
        
        #指令加载器,必须在后面
        container.register("CommandLoader", command_loader(self.config.file_path.commands))

        #LLM使用的tool
        container.register(
            "ToolCalls",
            tool_calls(self.config.file_path.tool_calls)
        )

        #多模态媒体转文本
        container.register("MediaProcessor", MediaProcessor())

        #处理模型响应
        container.register("LLMSupervisor", LLMCoordinator())

        #AIchat
        container.register("GroupChat", GroupChat())
        container.register("PrivateChat", PrivateChat())
        container.register("AgentChat", AgentChat())

    async def _start_admin_panel(self) -> None:
        """在独立端口启动 Web 管理面板"""
        from atribot.web_panel.panel_router import router as admin_router

        admin_app = FastAPI(title="ATRI Admin Panel", docs_url=None, redoc_url=None)
        admin_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost", "http://127.0.0.1"],
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
        admin_app.include_router(admin_router)

        admin_port = getattr(self.config.network, "admin_port", self.config.network.server_port + 1)
        cfg = uvicorn.Config(
            admin_app,
            host="127.0.0.1",
            port=admin_port,
            log_level="warning",
        )
        server = uvicorn.Server(cfg)
        self.logger.info(f"管理面板已就绪: http://127.0.0.1:{admin_port}/admin/")
        await server.serve()

    async def _start_network(self, server_type: str) -> None:
        """根据连接类型启动网络服务并开始消息监听"""
        if server_type == "WebSocket_server":
            ws: WebSocketServer = container.get("WebSocket")
            ws.add_listener(message_router().main)
            ws_task = self.create_background_task(ws.start())
            await ws.wait_for_connection()
            await ws_task

        elif server_type == "WebSocket_client":
            ws_client: WebSocketClient = container.get("WebSocket")
            ws_client.add_listener(message_router().main)
            await ws_client.start()

        elif server_type == "http":
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
                workers=8,
            )
            server = uvicorn.Server(uvicorn_app)
            await server.serve()
        else:
            raise ValueError(f"启动连接的时候接收了错误的连接类型:{server_type}")

    def create_background_task(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        """创建受控后台任务"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def graceful_shutdown(self) -> None:
        """等待关闭流程执行完成"""
        if self._shutdown_task is None:
            self._shutdown_task = asyncio.create_task(self.shutdown(), name="BotFramework.shutdown")

        try:
            await asyncio.shield(self._shutdown_task)
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            if current_task is not None:
                while current_task.cancelling():
                    current_task.uncancel()

            await self._shutdown_task
            raise

    async def shutdown(self) -> None:
        """关闭可显式回收的服务"""
        if self._is_shutdown:
            return

        self.logger.info("正在清理回收资源~")

        await container.shutdown()

        if self._background_tasks:
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()

            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()
        self._is_shutdown = True