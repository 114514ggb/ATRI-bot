import asyncio
import contextlib
from logging import Logger
from typing import Any, Awaitable

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from atribot.common_utils.http_client import HTTPClient
from atribot.common_utils.net_utils import try_bind_port
from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_loader import CommandLoader
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.event_bus.rule import AtCommandRule
from atribot.core.platform.manager import PlatformManager
from atribot.core.service_container import container
from atribot.core.time_trigger import TimeTriggerSupervisor
from atribot.core.type.bot_types import MessageEventEnvelope, atriMessageEvent
from atribot.LLMchat.chat import GroupChat, PrivateChat
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.initiative_chat import initiativeChat
from atribot.LLMchat.LLM_supervisor import LLMCoordinator
from atribot.LLMchat.MCP.mcp_tool_manager import ToolManager
from atribot.LLMchat.MCP.tool_calls import ToolCalls
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.memory.memory_system import MemorySystem
from atribot.LLMchat.memory.user_info_system import UserSystem
from atribot.LLMchat.message_sender import MessageSender
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.private_chat_trigger import privateChatTrigger
from atribot.LLMchat.sandbox.factory import create_sandbox, resolve_sandbox_config
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
        MessageSender,
        ChatManager,
        PermissionsManagement,
        CommandSystem,
        CommandLoader,
        PluginManager,
    )

    _NAMED_SERVICE_CLASSES = (
        (AsyncPostgreSQL, "database"),
        (ToolManager, "MCP"),
        (LLMConnectionManager, "LLMSupplier"),
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
        MessageSender,
        PermissionsManagement,
        ToolCalls,
        MediaProcessor,
        CommandSystem,
        CommandLoader,
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
        self._admin_server: uvicorn.Server | None = None
        """管理面板的 uvicorn 服务器，关闭时用于通知其平滑退出"""

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

        if not self._platform_manager.adapters:
            self.log.warning("没有可用适配器,系统处于不可以状态")

        await self._start_sandbox()
        await self._resolve_services()

        # 注册消息持久化
        await self._register_message_storage()

        # 注册 @ 路由监听器
        self._register_at_routes()

        # 启动所有平台适配器 + EventBus 主循环
        await self._platform_manager.start_all()

        await self._start_runtime_services()

    async def _register_message_storage(self) -> None:
        """注册内部处理中间件什么的"""
        from atribot.core.cache.message_store import store_message_to_db
        from atribot.core.pipeline.whitelist import WhitelistMiddleware
        
        #白名单
        await self._platform_manager.pipeline.add_middleware(WhitelistMiddleware())
        
        #存储
        self._platform_manager.queue.set_overflow_handler(store_message_to_db)
        self._platform_manager.event_bus.on_message(priority=101)(store_message_to_db)

    def _register_at_routes(self) -> None:
        """注册消息路由监听器到 EventBus

          10  @ + / 命令 → CommandSystem
           1  任意消息   → initiativeChat / privateChatTrigger
        """
        bus = self._platform_manager.event_bus
        log = self.log
        _initiative_chat = initiativeChat()
        _private_chat_trigger = privateChatTrigger()
        cmd_system = container.get_by_type(CommandSystem)

        @bus.on_message(rule=AtCommandRule(), priority=10)
        async def on_at_command(event:MessageEventEnvelope):
            try:
                await cmd_system.dispatch_command(event)
                event.stop_propagation = True
            except Exception as e:
                log.exception("命令处理失败: %s", e)
                await event.send(event.reply_text(f"ATRI用手挠了挠脑袋,这个指令执行出现了问题😕\nType Error:\n{e}"))
                event.stop_propagation = True

        @bus.on_message(priority=100)
        async def on_chat(event:atriMessageEvent):
            try:
                if group_context := event._extra.get("group_context"):
                    event.stop_propagation = await _initiative_chat.decision(event, group_context)
                elif event._extra.get("private_context"):
                    event.stop_propagation = await _private_chat_trigger.decision(event)
            except Exception as e:
                log.exception("聊天处理失败: %s", e)
                await event.send(event.reply_text(f"有关聊天的路由出现了问题:\n{e}\n你不应该看到这个的,因为最近在迁移方面的原因，有很多小毛病,看到这建议联系开发者"))

    def _register_services(self) -> None:
        """注册可由容器解析的服务类型"""
        for service_cls in self._SERVICE_CLASSES:
            container.register_class(service_cls)

        for service_cls, service_name in self._NAMED_SERVICE_CLASSES:
            container.register_class(service_cls, name=service_name)

    async def _start_sandbox(self) -> None:
        """启动 LLM 可选沙盒

        本地直执行(none)后端的工作区默认落在 ``document/work``；docker / e2b
        等隔离后端不受影响（容器内固定路径）。
        """
        raw_config: dict = getattr(self.config, "sand_box", None) or {}
        document_root = getattr(getattr(self.config, "file_path", None), "document_root", None)
        sandbox_config = resolve_sandbox_config(raw_config, document_root)
        try:
            sand_box = create_sandbox(sandbox_config)
            await sand_box.start()
            container.register("SandBox", sand_box, cleanup=sand_box.stop)
        except Exception as e:
            self.log.exception(f"LLM使用的沙盒初始化失败{e}")

    async def _resolve_services(self) -> None:
        """提前解析启动阶段需要的服务实例

        PluginManager 在此步被 resolve,其 initialize() 会自动：
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
        """在独立端口启动 Web 管理面板（web_panel.enable=false 时跳过）"""
        panel_cfg = self.config._raw_config.get("web_panel") or {}
        if panel_cfg.get("enable") is False:
            self.log.info("管理面板已在配置中禁用（web_panel.enable = false），跳过启动")
            return

        from atribot.web_panel.panel_router import _ensure_log_handler, mount_static
        from atribot.web_panel.panel_router import router as admin_router

        _ensure_log_handler()

        admin_app = FastAPI(title="ATRI Admin Panel", docs_url=None, redoc_url=None)
        admin_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost", "http://127.0.0.1"],
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
        admin_app.include_router(admin_router)
        mount_static(admin_app)

        @admin_app.get("/", include_in_schema=False)
        async def _redirect_to_admin():
            """访问根路径时重定向到管理面板"""
            return RedirectResponse(url="/admin/")

        admin_port = int(panel_cfg.get("port") or 5125)
        sock = try_bind_port("127.0.0.1", admin_port)
        if sock is None:
            self.log.warning(
                f"管理面板端口 127.0.0.1:{admin_port} 已被占用，本次跳过管理面板启动，"
                f"不影响机器人运行（请检查是否已有实例在运行，或修改 config 中 web_panel.port）"
            )
            return

        cfg = uvicorn.Config(
            admin_app,
            host="127.0.0.1",
            port=admin_port,
            log_level="warning",
            timeout_graceful_shutdown=3,
        )
        server = uvicorn.Server(cfg)

        server.capture_signals = lambda: contextlib.nullcontext()
        self._admin_server = server
        self.log.info(f"管理面板已就绪: http://127.0.0.1:{admin_port}/admin/")
        # 传入预绑定的 socket：绕开 uvicorn 绑定失败时内部 sys.exit 拖垮整个进程的分支
        await server.serve(sockets=[sock])

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
            if isinstance(exc, SystemExit):
                # SystemExit 仍会被事件循环继续抛出并终止进程，这里只留一行日志，不刷 traceback
                self.log.warning("后台任务请求退出进程: %s (exit code=%s)", task.get_name(), exc.code)
            else:
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

        await self._stop_admin_panel()
        await self._cancel_background_tasks()

        # 调度器没有注册容器 cleanup，这里显式停止，
        # 避免其主循环拖到事件循环收尾才被取消（关机日志会停在莫名的一行）
        if container.exists("TimeTriggerSupervisor"):
            try:
                await container.get("TimeTriggerSupervisor").stop()
            except Exception:
                self.log.exception("停止调度器失败，忽略并继续关闭")

        await container.shutdown()

        self._is_shutdown = True

    async def _stop_admin_panel(self) -> None:
        """通知管理面板平滑退出"""
        server = self._admin_server
        if server is None or server.should_exit:
            return

        server.should_exit = True
        panel_task = next(
            (t for t in self._background_tasks if t.get_name() == "BotFramework.admin_panel"),
            None,
        )
        if panel_task is None:
            return

        try:
            # uvicorn 的 timeout_graceful_shutdown=3，这里等待时间必须比它长：
            # 面板页还挂着 WebSocket 连接时，uvicorn 优雅关闭恰好需要约 3s，
            # 等待时间相等必然超时，导致 uvicorn 关闭被取消、内部任务残留到收尾
            await asyncio.wait_for(asyncio.shield(panel_task), timeout=8.0)
        except (TimeoutError, asyncio.CancelledError):
            # 强制退出标记：确保 panel_task 随后被取消时 uvicorn 能立即停下
            if self._admin_server is not None:
                self._admin_server.force_exit = True

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
