from __future__ import annotations

import asyncio
import json
import os
from contextlib import AsyncExitStack, suppress
from datetime import timedelta
from logging import Logger
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import mcp
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from atribot.common_utils.timer import retry as timer_retry
from atribot.core.atri_config import atriConfig
from atribot.core.service_container import ServiceBase, container
from atribot.LLMchat.MCP.tool_model import FunctionTool, MCPTool

DEFAULT_MCP_CONFIG = {"mcpServers": {}}


class MCPClient:
    def __init__(self):
        # 初始化会话和资源管理对象        
        self.logger:Logger = container.get("log")
        """日志配置"""
        self.session: Optional[mcp.ClientSession] = None  # MCP服务器会话
        self.exit_stack = AsyncExitStack()  # 异步上下文资源管理器

        self.name = None  # 客户端标识名
        self.active: bool = True  # 客户端激活状态
        self.tools: list["MCPTool"] = []  # 从服务器获取的工具列表（MCPTool 实例）
        self.server_errlogs: List[str] = []  # 服务器错误日志

        # 重连支持
        self._mcp_server_config: dict | None = None  # 保存原始配置用于重连
        self._server_name: str | None = None  # 服务名称
        self._reconnect_lock = asyncio.Lock()  # 重连互斥锁
        self._reconnecting: bool = False  # 重连状态标记
        self._old_exit_stacks: list[AsyncExitStack] = []  # 旧 exit_stack 延迟清理

    async def connect_to_server(self, mcp_server_config: dict, name: str | None = None):
        """连接到 MCP 服务器

        如果 `url` 参数存在：
            1. 当 transport 指定为 `streamable_http` 时，使用 Streamable HTTP 连接方式
            2. 当 transport 指定为 `sse` 时，使用 SSE 连接方式
            3. 如果没有指定，默认使用 SSE 的方式连接到 MCP 服务

        Args:
            mcp_server_config (dict): 服务器配置json
            name: MCP 服务名称，用于日志和重连标识
        """
        # 保存配置用于重连
        self._mcp_server_config = mcp_server_config
        if name is not None:
            self._server_name = name

        cfg = mcp_server_config.copy()
        if cfg.get("mcpServers"):
            cfg = dict(cfg["mcpServers"][next(iter(cfg["mcpServers"]))])
        else:
            cfg = dict(cfg)
        cfg.pop("active", None)

        if "url" in cfg:
            is_sse = True
            if cfg.get("transport") == "streamable_http":
                is_sse = False
            if is_sse:

                self._streams_context = sse_client(
                    url=cfg["url"],
                    headers=cfg.get("headers", {}),
                    timeout=cfg.get("timeout", 5),
                    sse_read_timeout=cfg.get("sse_read_timeout", 60 * 5),
                )
                streams = await self._streams_context.__aenter__()

                self.session = await self.exit_stack.enter_async_context(
                    mcp.ClientSession(*streams)
                )
            else:
                timeout = timedelta(seconds=cfg.get("timeout", 30))
                sse_read_timeout = timedelta(
                    seconds=cfg.get("sse_read_timeout", 60 * 5)
                )
                http_client = await self.exit_stack.enter_async_context(
                    create_mcp_http_client(
                        headers=cfg.get("headers", {}),
                        timeout=httpx.Timeout(
                            timeout.total_seconds(),
                            read=sse_read_timeout.total_seconds(),
                        ),
                    )
                )

                self._streams_context = streamable_http_client(
                    url=cfg["url"],
                    http_client=http_client,
                    terminate_on_close=cfg.get("terminate_on_close", True),
                )
                read_s, write_s, _ = await self.exit_stack.enter_async_context(
                    self._streams_context
                )

                self.session = await self.exit_stack.enter_async_context(
                    mcp.ClientSession(read_stream=read_s, write_stream=write_s)
                )

        else:
            server_params = mcp.StdioServerParameters(
                **cfg,
            )

            stdio_transport = await self.exit_stack.enter_async_context(
                mcp.stdio_client(
                    server_params
                ),
            )

            self.session = await self.exit_stack.enter_async_context(
                mcp.ClientSession(*stdio_transport)
            )

        await self.session.initialize()

    async def list_tools_and_save(self) -> mcp.ListToolsResult:
        """从服务器获取工具列表并保存到实例变量（MCPTool 实例）"""
        response = await self.session.list_tools()
        self.logger.info(f"MCP server {self.name}")
        self.tools = [
            MCPTool(
                name=tool.name,
                description=tool.description or "",
                parameters=tool.inputSchema,
                mcp_tool=tool,
                mcp_client=self,
                mcp_server_name=self.name or "",
            )
            for tool in response.tools
        ]
        return response

    async def _reconnect(self) -> None:
        """使用存储的配置重新连接至 MCP 服务器。

        使用 asyncio.Lock 确保并发环境中的线程安全重连。
        若已在重连中则跳过。

        Raises:
            Exception: 缺少连接配置或重连失败时抛出
        """
        async with self._reconnect_lock:
            if self._reconnecting:
                self.logger.debug(f"MCP 客户端 {self._server_name} 正在重连中，已跳过")
                return

            if not self._mcp_server_config or not self._server_name:
                raise Exception("无法重连: 缺少连接配置")

            self._reconnecting = True
            try:
                self.logger.info(f"正在尝试重连至 MCP 服务器 {self._server_name}...")

                # 保留旧 exit_stack 供延迟清理，避免影响其他任务上下文
                if self.exit_stack:
                    self._old_exit_stacks.append(self.exit_stack)

                # 置空旧会话
                self.session = None

                # 创建新 exit_stack 并重连
                self.exit_stack = AsyncExitStack()
                await self.connect_to_server(self._mcp_server_config, self._server_name)
                await self.list_tools_and_save()

                self.logger.info(f"成功重连至 MCP 服务器 {self._server_name}")
            except Exception as e:
                self.logger.error(f"重连至 MCP 服务器 {self._server_name} 失败: {e}")
                raise
            finally:
                self._reconnecting = False

    async def call_tool_with_retry(
        self,
        tool_name: str,
        arguments: dict,
        read_timeout_seconds: timedelta | None = None,
    ) -> Any:
        """调用 MCP 工具（支持出错后自动重连重试），最多重试 2 次。

        使用 timer.py 的 retry 装饰器实现重试逻辑，
        连接断开时自动触发 _reconnect() 后重试。

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            read_timeout_seconds: 读取超时时间

        Returns:
            MCP call_tool 方法的结果

        Raises:
            Exception: 重试耗尽后仍失败时抛出
        """

        @timer_retry(max_retries=2, interval=1.0, exceptions=(Exception,))
        async def _call_with_retry():
            if not self.session:
                raise Exception(f"MCP 会话不可用，无法调用工具 {tool_name}")

            try:
                call_kwargs: dict[str, Any] = {"name": tool_name, "arguments": arguments}
                if read_timeout_seconds is not None:
                    call_kwargs["read_timeout_seconds"] = read_timeout_seconds
                return await self.session.call_tool(**call_kwargs)
            except Exception:
                self.logger.warning(
                    f"MCP 工具 {tool_name} 调用失败，正在尝试重连..."
                )
                await self._reconnect()
                raise  # 重新抛出以触发 retry 装饰器重试

        return await _call_with_retry()

    async def cleanup(self):
        """清理所有异步资源，包括重连过程中保留的旧 exit_stack"""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            self.logger.debug(f"关闭当前 exit_stack 时出错: {e}")
        # 旧 exit_stack 交给 GC 处理，仅清空引用
        self._old_exit_stacks.clear()


class ToolManager(ServiceBase):
    """管理 MCP 连接生命周期"""

    def __init__(self, mcp_path: str | Path = "") -> None:
        self.logger: Logger = container.get("log")
        """日志配置"""
        self._mcp_func_list: List[FunctionTool] = []
        """MCP 服务发现的工具暂存区（不含本地工具），供 ToolCalls 拉取同步"""
        self.mcp_client_dict: Dict[str, MCPClient] = {}
        """MCP 服务列表"""
        self.mcp_service_queue = asyncio.Queue()
        """用于外部控制 MCP 服务的启停"""
        self.mcp_client_event: Dict[str, asyncio.Event] = {}
        """MCP客户端"""
        self.mcp_path: str | Path = mcp_path
        """MCP配置文件路径"""
        self._mcp_service_task: asyncio.Task | None = None
        """MCP 服务控制后台任务"""
        self._on_tools_changed: Callable[[str | None, List], None] | None = None
        """MCP 工具变更回调：(server_name | None, mcp_func_list) -> None"""

    @classmethod
    def factory(cls, config: atriConfig) -> ToolManager:
        instance = cls(config.file_path.mcp_config)
        instance._mcp_service_task = asyncio.create_task(instance.mcp_service_selector())
        instance.mcp_service_queue.put_nowait({"type": "init"})
        return instance

    async def cleanup(self) -> None:
        self.mcp_service_queue.put_nowait({"type": "terminate"})
        await asyncio.sleep(0)
        if self._mcp_service_task is not None:
            self._mcp_service_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._mcp_service_task
        self._mcp_service_task = None

    def set_on_tools_changed(
        self, callback: Callable[[str | None, List], None]
    ) -> None:
        """设置 MCP 工具变更回调，由 ToolCalls 在初始化时调用"""
        self._on_tools_changed = callback

    def get_mcp_func_tools(self) -> List:
        """返回当前 MCP 服务发现的工具列表（不含本地工具）"""
        return list(self._mcp_func_list)

    async def _notify_tools_changed(self, server_name: str | None = None) -> None:
        """触发工具变更回调"""
        if self._on_tools_changed is not None:
            await self._on_tools_changed(server_name, list(self._mcp_func_list))

    async def _init_mcp_clients(self) -> None:
        """读取 mcp_server.json 文件，初始化 MCP 服务列表。文件格式如下：
        ```
        {
            "mcpServers": {
                "weather": {
                    "command": "uv",
                    "args": [
                        "--directory",
                        "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather",
                        "run",
                        "weather.py"
                    ]
                }
            }
            ...
        }
        ```
        """
        mcp_json_file = os.path.join(self.mcp_path)
        if not os.path.exists(mcp_json_file):
            # 配置文件不存在错误处理
            with open(mcp_json_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_MCP_CONFIG, f, ensure_ascii=False, indent=4)
            self.logger.info(f"未找到 MCP 服务配置文件，已创建默认配置文件 {mcp_json_file}")
            return

        mcp_server_json_obj: Dict[str, Dict] = json.load(
            open(mcp_json_file, "r", encoding="utf-8")
        )["mcpServers"]

        for name in mcp_server_json_obj.keys():
            cfg = mcp_server_json_obj[name]
            if cfg.get("active", True):
                event = asyncio.Event()
                asyncio.create_task(
                    self._init_mcp_client_task_wrapper(name, cfg, event)
                )
                self.mcp_client_event[name] = event

    async def mcp_service_selector(self):
        """为了避免在不同异步任务中控制 MCP 服务导致的报错，整个项目统一通过这个 Task 来控制

        使用 self.mcp_service_queue.put_nowait() 来控制 MCP 服务的启停，数据格式如下：

        {"type": "init"} 初始化所有MCP客户端

        {"type": "init", "name": "mcp_server_name", "cfg": {...}} 初始化指定的MCP客户端

        {"type": "terminate"} 终止所有MCP客户端

        {"type": "terminate", "name": "mcp_server_name"} 终止指定的MCP客户端
        """
        while True:
            data = await self.mcp_service_queue.get()
            if data["type"] == "init":
                if "name" in data:
                    event = asyncio.Event()
                    asyncio.create_task(
                        self._init_mcp_client_task_wrapper(
                            data["name"], data["cfg"], event
                        )
                    )
                    self.mcp_client_event[data["name"]] = event
                else:
                    await self._init_mcp_clients()
            elif data["type"] == "terminate":
                if "name" in data:
                    if data["name"] in self.mcp_client_event:
                        self.mcp_client_event[data["name"]].set()
                        self.mcp_client_event.pop(data["name"], None)
                        self._mcp_func_list = [
                            f
                            for f in self._mcp_func_list
                            if not (
                                isinstance(f, MCPTool) and f.mcp_server_name == data["name"]
                            )
                        ]
                        await self._notify_tools_changed(data["name"])
                else:
                    for name in self.mcp_client_dict.keys():
                        if name in self.mcp_client_event:
                            self.mcp_client_event[name].set()
                            self.mcp_client_event.pop(name, None)
                    self._mcp_func_list = [f for f in self._mcp_func_list if not isinstance(f, MCPTool)]
                    await self._notify_tools_changed()

    async def _init_mcp_client_task_wrapper(
        self, name: str, cfg: dict, event: asyncio.Event
    ) -> None:
        """初始化 MCP 客户端的包装函数，用于捕获异常"""
        try:
            await self._init_mcp_client(name, cfg)
            await event.wait()
            self.logger.info(f"收到 MCP 客户端 {name} 终止信号")
            await self._terminate_mcp_client(name)
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.logger.error(f"初始化 MCP 客户端 {name} 失败: {e}")

    async def _init_mcp_client(self, name: str, config: dict) -> None:
        """初始化单个MCP客户端"""
        try:
            # 先清理之前的客户端，如果存在
            if name in self.mcp_client_dict:
                await self._terminate_mcp_client(name)

            mcp_client = MCPClient()
            mcp_client.name = name
            self.mcp_client_dict[name] = mcp_client
            await mcp_client.connect_to_server(config)
            tools_res = await mcp_client.list_tools_and_save()
            tool_names = [tool.name for tool in tools_res.tools]

            # 移除该MCP服务之前的工具（如有）
            self._mcp_func_list = [
                f
                for f in self._mcp_func_list
                if not (isinstance(f, MCPTool) and f.mcp_server_name == name)
            ]

            # 将 MCP 工具转换为 MCPTool 并添加到 _mcp_func_list
            for tool in mcp_client.tools:
                func_tool = MCPTool(
                    name=tool.name,
                    parameters=tool.parameters,
                    description=tool.description,
                    mcp_tool=tool,
                    mcp_client=mcp_client,
                    mcp_server_name=name,
                )
                self._mcp_func_list.append(func_tool)

            self.logger.info(f"已连接 MCP 服务 {name}, Tools: {tool_names}")
            await self._notify_tools_changed(name)
            return
        except Exception as e:
            import traceback

            self.logger.info(traceback.format_exc())
            self.logger.error(f"初始化 MCP 客户端 {name} 失败: {e}")
            # 发生错误时确保客户端被清理
            if name in self.mcp_client_dict:
                await self._terminate_mcp_client(name)
            return

    async def _terminate_mcp_client(self, name: str) -> None:
        """关闭并清理MCP客户端"""
        if name in self.mcp_client_dict:
            try:
                # 关闭MCP连接
                await self.mcp_client_dict[name].cleanup()
                del self.mcp_client_dict[name]
            except Exception as e:
                self.logger.info(f"清空 MCP 客户端资源 {name}: {e}。")
            # 移除关联的 FunctionTool
            self._mcp_func_list = [
                f
                for f in self._mcp_func_list
                if not (isinstance(f, MCPTool) and f.mcp_server_name == name)
            ]
            self.logger.info(f"已关闭 MCP 服务 {name}")
            await self._notify_tools_changed(name)

    def __str__(self):
        return str(self._mcp_func_list)

    def __repr__(self):
        return str(self._mcp_func_list)

    async def terminate(self):
        """关闭清理"""
        for name in list(self.mcp_client_dict.keys()):
            await self._terminate_mcp_client(name)
            self.logger.info(f"清理 MCP 客户端 {name} 资源")
