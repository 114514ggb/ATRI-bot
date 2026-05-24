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
from atribot.LLMchat.chat import GroupChat, PrivateChat
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
from atribot.LLMchat.token_manage import TokenManager


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
        self.config = atriConfig()
        container.register("config", self.config)
        container.register_class(atriConfig)
        container.register_class(HTTPClient)
        container.register_class(TimeTriggerSupervisor)
        container.register_class(TokenManager)
        container.register_class(memorySystem)
        container.register_class(UserSystem)
        container.register_class(EventTrigger)
        container.register_class(CommandSystem)
        container.register_class(MediaProcessor)
        container.register_class(LLMCoordinator)
        container.register_class(GroupChat)
        container.register_class(PrivateChat)
        container.register_class(SkillsManager)
        container.register_class(EmojiCore)
        container.register_class(ChatManager)
        container.register_class(PermissionsManagement)
        container.register_class(AsyncPostgreSQL, name="database")
        container.register_class(FuncCall, name="MCP")
        container.register_class(LLMConnectionManager, name="LLMSupplier")
        container.register_class(QQAPIClient, name="SendMessage")
        container.register_class(tool_calls, name="ToolCalls")
        
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

        # ai使用的沙盒 (可选)
        try:
            sand_box:SandBoxBase = DockerSandbox(config=self.config.sand_box)
            await sand_box.start()
            container.register("SandBox", sand_box, cleanup=sand_box.stop)
        except Exception as e:
            self.logger.exception(f"LLM使用的沙盒初始化失败{e}")

        resolve_targets = [
            HTTPClient, TimeTriggerSupervisor, FuncCall, AsyncPostgreSQL,
            TokenManager, LLMConnectionManager, SkillsManager, memorySystem,
            UserSystem, ChatManager, EmojiCore, PermissionsManagement,
            QQAPIClient, EventTrigger, CommandSystem, tool_calls,
            MediaProcessor, LLMCoordinator, GroupChat, PrivateChat
        ]
        
        for tgt in resolve_targets:
            await container.resolve(tgt)
            
        # 指令加载器
        container.register("CommandLoader", command_loader(self.config.file_path.commands))

        #后置激活项
        trigger = container.get_by_type(TimeTriggerSupervisor)
        await trigger.start()

        # 管理面板
        self.create_background_task(self._start_admin_panel())

        await self._start_network(server_type)


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