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

    _SERVICE_CLASSES = (
        atriConfig,
        HTTPClient,
        TimeTriggerSupervisor,
        TokenManager,
        memorySystem,
        UserSystem,
        EventTrigger,
        CommandSystem,
        MediaProcessor,
        LLMCoordinator,
        GroupChat,
        PrivateChat,
        SkillsManager,
        EmojiCore,
        ChatManager,
        PermissionsManagement,
    )

    _NAMED_SERVICE_CLASSES = (
        (AsyncPostgreSQL, "database"),
        (FuncCall, "MCP"),
        (LLMConnectionManager, "LLMSupplier"),
        (QQAPIClient, "SendMessage"),
        (tool_calls, "ToolCalls"),
    )

    _RESOLVE_TARGETS = (
        HTTPClient,
        TimeTriggerSupervisor,
        FuncCall,
        AsyncPostgreSQL,
        TokenManager,
        LLMConnectionManager,
        SkillsManager,
        memorySystem,
        UserSystem,
        ChatManager,
        EmojiCore,
        PermissionsManagement,
        QQAPIClient,
        EventTrigger,
        CommandSystem,
        tool_calls,
        MediaProcessor,
        LLMCoordinator,
        GroupChat,
        PrivateChat,
    )
    
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

        self._register_services()

        server_type: str = self.config.network.connection_type
        self._register_network(server_type)

        await self._start_sandbox()
        await self._resolve_services()
        await self._start_runtime_services()

        await self._start_network(server_type)

    def _register_services(self) -> None:
        """注册可由容器解析的服务类型"""
        for service_cls in self._SERVICE_CLASSES:
            container.register_class(service_cls)

        for service_cls, service_name in self._NAMED_SERVICE_CLASSES:
            container.register_class(service_cls, name=service_name)

    def _register_network(self, server_type: str) -> None:
        """按连接类型注册网络连接实例"""
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

    async def _start_sandbox(self) -> None:
        """启动 LLM 可选沙盒"""
        try:
            sand_box: SandBoxBase = DockerSandbox(config=self.config.sand_box)
            await sand_box.start()
            container.register("SandBox", sand_box, cleanup=sand_box.stop)
        except Exception as e:
            self.logger.exception(f"LLM使用的沙盒初始化失败{e}")

    async def _resolve_services(self) -> None:
        """提前解析启动阶段需要的服务实例"""
        for tgt in self._RESOLVE_TARGETS:
            await container.resolve(tgt)
        
        container.register("CommandLoader", command_loader(self.config.file_path.commands))

    async def _start_runtime_services(self) -> None:
        """启动依赖容器完成后的运行期服务"""
        trigger = container.get_by_type(TimeTriggerSupervisor)
        await trigger.start()

        self.create_background_task(self._start_admin_panel(), name="BotFramework.admin_panel")

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
            ws_task = self.create_background_task(ws.start(), name="BotFramework.websocket_server")
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
                self.create_background_task(_message_router.main(data), name="BotFramework.http_event")
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

    def create_background_task(self, coro: Awaitable[Any], *, name: str | None = None) -> asyncio.Task[Any]:
        """创建受控后台任务"""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._handle_background_task_done)
        return task

    def _handle_background_task_done(self, task: asyncio.Task[Any]) -> None:
        """清理后台任务引用并记录异常"""
        self._background_tasks.discard(task)
        if task.cancelled():
            return

        if exc := task.exception():
            self.logger.exception("后台任务异常退出: %s", task.get_name(), exc_info=exc)

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

        await self._cancel_background_tasks()
        await container.shutdown()

        self._is_shutdown = True

    async def _cancel_background_tasks(self) -> None:
        """取消并等待所有受控后台任务"""
        if not self._background_tasks:
            return

        tasks = list(self._background_tasks)
        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()
