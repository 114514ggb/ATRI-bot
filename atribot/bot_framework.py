import asyncio
from logging import Logger
from typing import Any, Awaitable

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atribot.common_utils.http_client import HTTPClient
from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.cache.message_store import store_message_to_db
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.pipeline.whitelist import WhitelistMiddleware
from atribot.core.platform.manager import PlatformManager
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.LLMchat.chat import GroupChat, PrivateChat
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.LLM_supervisor import LLMCoordinator
from atribot.LLMchat.MCP.mcp_tool_manager import ToolManager
from atribot.LLMchat.MCP.tool_calls import ToolCalls
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.memory.memory_system import MemorySystem
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase
from atribot.LLMchat.skills.skills_manager import SkillsManager
from atribot.LLMchat.token_manage import TokenManager
from atribot.plugins.manager import PluginManager


class BotFramework:

    _SERVICE_CLASSES = (
        atriConfig,
        HTTPClient,
        TimeTriggerSupervisor,
        TokenManager,
        MemorySystem,
        UserSystem,
        MediaProcessor,
        LLMCoordinator,
        GroupChat,
        PrivateChat,
        SkillsManager,
        EmojiCore,
        ChatManager,
        PermissionsManagement,
        PluginManager,
    )

    _NAMED_SERVICE_CLASSES = (
        (AsyncPostgreSQL, "database"),
        (ToolManager, "MCP"),
        (LLMConnectionManager, "LLMSupplier"),
        # (QQAPIClient, "SendMessage"),
        (ToolCalls, "ToolCalls"),
    )

    _RESOLVE_TARGETS = (
        HTTPClient,
        TimeTriggerSupervisor,
        ToolManager,
        AsyncPostgreSQL,
        TokenManager,
        LLMConnectionManager,
        SkillsManager,
        MemorySystem,
        UserSystem,
        ChatManager,
        EmojiCore,
        PermissionsManagement,
        # QQAPIClient,
        ToolCalls,
        MediaProcessor,
        LLMCoordinator,
        GroupChat,
        PrivateChat,
        PluginManager,
    )

    def __init__(self):
        self.log: Logger = container.get_by_type(Logger).getChild("Bot")
        self._background_tasks: set[asyncio.Task[Any]] = set()
        """退出时统一回收的后台任务"""
        self._shutdown_task: asyncio.Task[None] | None = None
        self._is_shutdown = False
        """标记是否已经完成关闭"""
        self._platform_manager: PlatformManager | None = None
        """平台管理器实例"""

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

        self._platform_manager = PlatformManager(self.config)
        container.register("PlatformManager", self._platform_manager, cleanup=self._platform_manager.stop_all)
        container._type_map[PlatformManager] = "PlatformManager"

        if self._platform_manager.adapters:
            _first_adapter = next(iter(self._platform_manager.adapters.values()))
            _send_client = _first_adapter.get_client()
            container.register("SendMessage", _send_client)
            container._type_map[QQAPIClient] = "SendMessage"
            self.log.info(
                "SendMessage 已桥接到适配器 '%s' (%s)",
                next(iter(self._platform_manager.adapters.keys())),
                type(_send_client).__name__,
            )
        else:
            self.log.warning("没有可用适配器,SendMessage 未注册")

        #白名单
        await self._platform_manager.pipeline.add_middleware(WhitelistMiddleware())
        
        #存储
        self._platform_manager.queue.set_overflow_handler(store_message_to_db)
        self._platform_manager.event_bus.on_message(priority=-100)(store_message_to_db)

        await self._start_sandbox()
        await self._resolve_services()

        # 启动所有平台适配器 + EventBus 主循环
        await self._platform_manager.start_all()

        await self._start_runtime_services()

    def _register_services(self) -> None:
        """注册可由容器解析的服务类型"""
        for service_cls in self._SERVICE_CLASSES:
            container.register_class(service_cls)

        for service_cls, service_name in self._NAMED_SERVICE_CLASSES:
            container.register_class(service_cls, name=service_name)

    async def _start_sandbox(self) -> None:
        """启动 LLM 可选沙盒"""
        try:
            sand_box: SandBoxBase = DockerSandbox(config=self.config.sand_box)
            await sand_box.start()
            container.register("SandBox", sand_box, cleanup=sand_box.stop)
        except Exception as e:
            self.log.exception(f"LLM使用的沙盒初始化失败{e}")

    async def _resolve_services(self) -> None:
        """提前解析启动阶段需要的服务实例

        PluginManager 在此步被 resolve，其 initialize() 会自动：
        1. 从容器获取 PlatformManager
        2. 创建 PluginLoader 扫描 atribot/plugins/
        3. 加载所有插件，插件自动将 handlers 注册到 EventBus
        """
        for tgt in self._RESOLVE_TARGETS:
            await container.resolve(tgt)

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
        self.log.info(f"管理面板已就绪: http://127.0.0.1:{admin_port}/admin/")
        await server.serve()

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
            self.log.exception("后台任务异常退出: %s", task.get_name(), exc_info=exc)

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

        self.log.info("正在清理回收资源~")

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
