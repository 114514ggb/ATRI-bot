import asyncio
from inspect import isawaitable
from logging import Logger
from typing import Any, Awaitable, Callable, Dict

import uvicorn
from fastapi import FastAPI

from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_loader import command_loader
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_postgresql import AsyncPostgreSQL
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
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.model_api.bigModel_api import AsyncBigModelApi
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase
from atribot.LLMchat.skills.skills_manager import SkillsManager


class BotFramework:
    """主初始化类"""
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self._shutdown_handlers: dict[str, Callable[[], Any | Awaitable[Any]]] = {}
        """保存各组件注册的清理函数"""
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
        
        # 时间触发器,后面服务会依赖就只能放最前面了
        TriggerSupervisor = TimeTriggerSupervisor()
        container.register(
            "TimeTriggerSupervisor",
            TriggerSupervisor
        )
        self.register_shutdown_handler("TimeTriggerSupervisor", TriggerSupervisor.stop)
        
        #MCP
        mcp_server = FuncCall(self.config.file_path.mcp_config)
        self.create_background_task(mcp_server.mcp_service_selector())#放到后台不等待
        mcp_server.mcp_service_queue.put_nowait({"type": "init"})#初始化
        container.register(
            "MCP",
            mcp_server
        )
        self.register_shutdown_handler("MCP", mcp_server.terminate)
        
        #数据库
        database = await AsyncPostgreSQL.create(
            host = self.config.database.host, 
            user = self.config.database.user,
            port = self.config.database.port,
            password = self.config.database.password
        )
        container.register(
            "database",
            database
        )
        self.register_shutdown_handler("database", database.close_pool)
        
        #模型供应商
        LLMSupplier = LLMConnectionManager()
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
        self.register_shutdown_handler("LLMSupplier", LLMSupplier.close)
        
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
            self.register_shutdown_handler("SandBox", sand_box.stop)
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

        # ── 阶段一：注册 WebSocket 连接对象 ──────────────────────────────────────
        # QQAPIClient 在 WS 模式下 __init__ 时会直接从容器获取 WebSocket，
        # 因此必须在 _init_messaging_services() 之前完成注册。
        server_type: str = self.config.network.connection_type
        if server_type == "WebSocket_server":
            ws = WebSocketServer(
                host=self.config.network.host,
                port=self.config.network.server_port,
                access_token=self.config.network.access_token,
            )
            container.register("WebSocket", ws)
            self.register_shutdown_handler("WebSocket", ws.close)
        elif server_type == "WebSocket_client":
            ws = WebSocketClient(
                url=self.config.network.url,
                access_token=self.config.network.access_token,
            )
            container.register("WebSocket", ws)
            self.register_shutdown_handler("WebSocket", ws.close)
        elif server_type != "http":
            raise ValueError(f"不支持的连接类型: {server_type}")

        # ── 阶段二：初始化依赖 WebSocket 的消息服务及上层应用 ────────────────────
        self._init_messaging_services()

        # ── 阶段三：启动网络连接，开始收发消息 ───────────────────────────────────
        await self._start_network(server_type)

    def _init_messaging_services(self) -> None:
        """初始化消息发送及依赖它的上层应用服务。

        前置依赖（WS 模式）：WebSocket 对象必须已注册到容器，
        因为 QQAPIClient 在 __init__ 时会立即从容器获取 WebSocket 单例。

        注册顺序：SendMessage → CommandSystem → CommandLoader → LLMSupervisor → GroupChat
        """
        send_message = QQAPIClient(
            token=self.config.network.access_token,
            http_base_url=self.config.network.url,
            connection_type=self.config.network.connection_type,
        )
        container.register("SendMessage", send_message)

        # 指令系统（__init__ 时依赖 SendMessage、PermissionsManagement）
        container.register("CommandSystem", CommandSystem())
        container.register("CommandLoader", command_loader(self.config.file_path.commands))

        # LLM 协调与对话（GroupChat.__init__ 依赖几乎所有已注册服务）
        container.register("LLMSupervisor", LLMCoordinator())
        container.register("GroupChat", GroupChat())

    async def _start_network(self, server_type: str) -> None:
        """根据连接类型启动网络服务并开始消息监听。所有服务应在此前初始化完毕。"""
        if server_type == "WebSocket_server":
            ws: WebSocketServer = container.get("WebSocket")
            ws.add_listener(message_router().main)
            # start() 内含无限循环，需以后台任务运行；
            # wait_for_connection() 等待 NapCat 首次接入后返回，再持续阻塞在任务上。
            ws_task = self.create_background_task(ws.start())
            await ws.wait_for_connection()
            await ws_task

        elif server_type == "WebSocket_client":
            ws_client: WebSocketClient = container.get("WebSocket")
            ws_client.add_listener(message_router().main)
            await ws_client.start()

        else:  # http
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

    def register_shutdown_handler(
        self,
        name: str,
        handler: Callable[[], Any | Awaitable[Any]]
    ) -> None:
        """注册关闭阶段需要执行的清理函数"""
        if name in self._shutdown_handlers:
            raise ValueError(f"清理函数已注册: {name}")
        self._shutdown_handlers[name] = handler

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

        for name, handler in reversed(list(self._shutdown_handlers.items())):
            try:
                result = handler()
                if isawaitable(result):
                    await result
                self.logger.debug(f"资源已关闭:{name}")
            except Exception as e:
                self.logger.exception(f"关闭资源失败 [{name}]: {e}")

        if self._background_tasks:
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()

            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()

        self._shutdown_handlers.clear()
        self._is_shutdown = True