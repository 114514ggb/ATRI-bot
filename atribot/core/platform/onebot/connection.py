import asyncio
import asyncio as _asyncio
import inspect
import json
import logging
import uuid
from asyncio import CancelledError, Event, Task, create_task, gather, sleep
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.datastructures import Headers
from websockets.legacy.client import WebSocketClientProtocol
from websockets.legacy.server import Serve, WebSocketServerProtocol
from websockets.legacy.server import WebSocketServer as WSServer


class OneBotWSClient:
    """OneBot WebSocket 正向连接客户端"""

    def __init__(
        self,
        url: str = "127.0.0.1:8080",
        access_token: Optional[str] = None,
        max_retries: int = 120,
        retry_delay: float = 1.0,
        echo_timeout: float = 15.0,
        log: logging.Logger | None = None,
    ):
        self.url = url
        self.access_token = access_token
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.echo_timeout = echo_timeout

        self.log = log or logging.getLogger("OneBotWSClient")

        # 连接状态
        self.websocket: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._connected = Event()
        self._retry_count = 0

        # 消息处理
        self.pending_requests: dict[str, asyncio.Future] = {}
        self._listeners: list[Callable] = []

        # 任务管理
        self._tasks: list[Task] = []

    def _build_uri(self) -> str:
        """构建 WebSocket URI"""
        protocol = "ws://"
        if self.access_token:
            uri = f"{protocol}{self.url}/websocket?access_token={self.access_token}"
        else:
            uri = f"{protocol}{self.url}/"
        self.log.info("目标 URI: %s", uri.replace(self.access_token or "", "***") if self.access_token else uri)
        return uri

    async def _connect(self) -> None:
        """连接到 WebSocket 服务器"""
        self.log.info("正在尝试连接 %s ...", self.url)
        while self._retry_count < self.max_retries and self._running:
            try:
                self.websocket = await websockets.connect(
                    self._build_uri(),
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                )
                self.log.info("WebSocket 连接成功: %s (耗时 %.1fs)", self.url, self._retry_count * self.retry_delay)
                self._retry_count = 0
                self._connected.set()
                return
            except Exception as e:
                self._retry_count += 1
                self._connected.clear()
                if self._retry_count >= self.max_retries:
                    self.log.error(
                        "连接失败，已达最大重试次数 %d 次: %s",
                        self.max_retries, e,
                    )
                    raise
                self.log.warning(
                    "连接失败 (第%d次): %s, %.1f秒后重试...",
                    self._retry_count, e, self.retry_delay,
                )
                await sleep(self.retry_delay)

    async def start(self) -> None:
        """启动客户端"""
        if self._running:
            return
        self._running = True

        await self._connect()

        self._tasks = [
            create_task(self._receive_messages()),
        ]

        try:
            await gather(*self._tasks, return_exceptions=False)
        except CancelledError:
            pass
        except Exception as e:
            self.log.exception("事件循环异常: %s", e)
        finally:
            self._running = False

    async def _receive_messages(self) -> None:
        """接收消息并分发给所有监听器"""
        while self._running:
            try:
                if not self.websocket:
                    await self._connected.wait()
                    continue

                data = json.loads(await self.websocket.recv())
                
                # 处理 echo 响应
                if "echo" in data and data["echo"]:
                    echo_id = data["echo"]
                    if echo_id in self.pending_requests:
                        future = self.pending_requests.pop(echo_id)
                        if not future.done():
                            future.set_result(data)
                    continue

                for listener in self._listeners:
                    await self._safe_callback(listener, data)

            except json.JSONDecodeError as e:
                self.log.error("JSON 解析错误: %s", e)
            except websockets.exceptions.ConnectionClosed as e:
                self._connected.clear()
                if e.code == 1005:
                    self.log.info("WebSocket 连接正常关闭 (code=1005)")
                else:
                    self.log.warning("WebSocket 连接异常关闭: code=%s %s", e.code, e)
                if self._running:
                    self.log.info("正在重新连接...")
                    await self._connect()
                    self.log.info("重新连接成功")
            except Exception as e:
                self.log.error("接收消息时发生错误: %s", e)
                if self._running:
                    self._connected.clear()
                    self.log.info("将在 %.1f 秒后重试...", self.retry_delay)
                    await sleep(self.retry_delay)
                    await self._connect()

    @staticmethod
    async def _safe_callback(callback: Callable, data: dict) -> None:
        """安全执行回调函数"""
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(data)
            else:
                await _asyncio.to_thread(callback, data)
        except Exception:
            logging.getLogger("OneBotWSClient").exception(
                "回调执行错误: %s", callback
            )

    async def send(self, data: dict, with_echo: bool = False) -> Optional[dict]:
        """发送消息

        Args:
            data: 要发送的数据字典
            with_echo: 是否等待并返回 echo 响应

        Returns:
            echo 响应字典(with_echo=True 时），否则 None
        """
        if with_echo:
            echo_id = str(uuid.uuid4())
            data["echo"] = echo_id

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self.pending_requests[echo_id] = future

            try:
                if self.websocket:
                    await self.websocket.send(json.dumps(data))
                return await asyncio.wait_for(future, timeout=self.echo_timeout)
            except asyncio.TimeoutError:
                self.pending_requests.pop(echo_id, None)
                raise TimeoutError(f"等待 echo 响应超时 ({self.echo_timeout}秒)")
            except Exception:
                self.pending_requests.pop(echo_id, None)
                raise
        else:
            if self.websocket:
                await self.websocket.send(json.dumps(data))
            return None

    def add_listener(self, callback: Callable[[dict], Any]) -> None:
        """添加消息监听器"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict], Any]) -> None:
        """移除消息监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def close(self) -> None:
        """优雅关闭连接"""
        self._running = False
        self._connected.clear()

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await gather(*self._tasks, return_exceptions=True)

        # 关闭 WebSocket 连接
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        # 清理资源
        self._listeners.clear()
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()

        self.log.info("WebSocket 客户端已关闭")

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.websocket is not None and not self.websocket.closed

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


class OneBotWSServer:
    """OneBot WebSocket 反向连接服务端"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        access_token: Optional[str] = None,
        echo_timeout: float = 15.0,
        log: logging.Logger | None = None,
    ):
        self.host = host
        self.port = port
        self.access_token = access_token
        self.echo_timeout = echo_timeout

        self.log = log or logging.getLogger("OneBotWSServer")

        # 连接状态
        self.websocket: Optional[WebSocketServerProtocol] = None
        self._running = False
        self._connected = Event()
        self._server: Optional[WSServer] = None

        # 消息处理
        self.pending_requests: dict[str, asyncio.Future] = {}
        self._listeners: list[Callable] = []

        # 任务管理
        self._tasks: list[Task] = []

    def _verify_token(self, path: str, headers: Headers) -> bool:
        """验证访问令牌（Header 或 URL 参数）"""
        if not self.access_token:
            return True

        # Header: Authorization: Bearer <token>
        if auth_header := headers.get("Authorization"):
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                input_token = parts[1]
            else:
                input_token = auth_header
            self.log.debug("检测到 Header 认证信息: %s", input_token)
            if input_token == self.access_token:
                return True

        # URL 参数: ?access_token=<token>
        query = urlparse(path).query
        params = parse_qs(query)
        for key in ("access_token", "token"):
            if key in params and params[key][0] == self.access_token:
                return True

        return False

    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """处理客户端连接"""
        if not self._verify_token(path, websocket.request_headers):
            self.log.warning("客户端连接被拒绝: 无效的 access_token")
            await websocket.close(1008, "Invalid access token")
            return

        # 如果已有连接，断开旧连接
        if self.websocket and self.websocket.open:
            self.log.info("断开旧连接，接受新连接")
            await self.websocket.close()

        self.websocket = websocket
        self._connected.set()
        self.log.info("客户端已连接: %s", websocket.remote_address)

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    # 处理 echo 响应
                    if "echo" in data and data["echo"]:
                        echo_id = data["echo"]
                        if echo_id in self.pending_requests:
                            future = self.pending_requests.pop(echo_id)
                            if not future.done():
                                future.set_result(data)
                        continue

                    for listener in self._listeners:
                        await self._safe_callback(listener, data)

                except json.JSONDecodeError as e:
                    self.log.error("JSON 解析错误: %s", e)
                except Exception as e:
                    self.log.error("处理消息时发生错误: %s", e)

        except Exception as e:
            self.log.error("连接处理异常: %s", e)
        finally:
            if self.websocket == websocket:
                self.websocket = None
                self._connected.clear()
                self.log.info("客户端已断开连接")

    async def start(self) -> None:
        """启动服务端"""
        if self._running:
            return
        self._running = True

        self._server = await Serve(
            self._handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10,
        )
        self.log.info("WebSocket 服务器已启动: ws://%s:%d", self.host, self.port)

        self._tasks = []

        try:
            await gather(*self._tasks, return_exceptions=False)
        except CancelledError:
            pass
        except Exception as e:
            self.log.exception("事件循环异常: %s", e)
        finally:
            self._running = False

    @staticmethod
    async def _safe_callback(callback: Callable, data: dict) -> None:
        """安全执行异步回调函数"""
        try:
            await callback(data)
        except Exception:
            logging.getLogger("OneBotWSServer").exception(
                "回调执行错误: %s", callback
            )

    async def send(self, data: dict, with_echo: bool = False) -> Optional[dict]:
        """发送消息"""
        if with_echo:
            echo_id = str(uuid.uuid4())
            data["echo"] = echo_id

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self.pending_requests[echo_id] = future

            try:
                if self.websocket:
                    await self.websocket.send(json.dumps(data))
                return await asyncio.wait_for(future, timeout=self.echo_timeout)
            except asyncio.TimeoutError:
                self.pending_requests.pop(echo_id, None)
                raise TimeoutError(f"等待 echo 响应超时 ({self.echo_timeout}秒)")
            except Exception:
                self.pending_requests.pop(echo_id, None)
                raise
        else:
            if self.websocket:
                await self.websocket.send(json.dumps(data))
            return None

    def add_listener(self, callback: Callable[[dict], Any]) -> None:
        """添加消息监听器"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict], Any]) -> None:
        """移除消息监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """等待客户端连接

        Args:
            timeout: 超时时间(秒),None 表示无限等待

        Returns:
            是否在超时前成功连接
        """
        try:
            if timeout:
                await asyncio.wait_for(self._connected.wait(), timeout=timeout)
            else:
                await self._connected.wait()
            return True
        except asyncio.TimeoutError:
            return False

    async def close(self) -> None:
        """优雅关闭服务器"""
        self._running = False
        self._connected.clear()

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await gather(*self._tasks, return_exceptions=True)

        # 关闭客户端连接
        if self.websocket and self.websocket.open:
            await self.websocket.close()
            self.websocket = None

        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # 清理资源
        self._listeners.clear()
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()

        self.log.info("WebSocket 服务器已关闭")

    @property
    def is_connected(self) -> bool:
        """检查客户端是否已连接"""
        return self.websocket is not None and self.websocket.open

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


class OneBotHttpServer:
    """OneBot HTTP 服务端"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        access_token: Optional[str] = None,
        log: logging.Logger | None = None,
    ):
        self.host = host
        self.port = port
        self.access_token = access_token
        self.log = log or logging.getLogger("OneBotHttpServer")

        self._listeners: list[Callable[[dict], Any]] = []
        self._running = False
        self._uvicorn_server = None

    def add_listener(self, callback: Callable[[dict], Any]) -> None:
        """添加事件监听器"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict], Any]) -> None:
        """移除事件监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def start(self) -> None:
        """启动 HTTP 服务器，监听 POST / 接收事件"""
        if self._running:
            return
        self._running = True

        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse

        app = FastAPI()

        @app.post("/")
        async def handle_event(request: Request):
            if self.access_token:
                auth = request.headers.get("Authorization", "")
                if auth != f"Bearer {self.access_token}":
                    self.log.warning("HTTP 请求认证失败")
                    return JSONResponse(status_code=401, content={"error": "Unauthorized"})

            try:
                data = await request.json()
            except Exception as e:
                self.log.warning("JSON 解析失败: %s", e)
                return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

            tasks = [
                asyncio.create_task(self._safe_callback(listener, data))
                for listener in self._listeners
            ]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            return {"status": "ok"}

        import uvicorn

        cfg = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        self._uvicorn_server = uvicorn.Server(cfg)
        self.log.info("HTTP 服务器已启动: http://%s:%d", self.host, self.port)
        try:
            await self._uvicorn_server.serve()
        finally:
            self._running = False

    @staticmethod
    async def _safe_callback(callback: Callable[[dict], Any], data: dict) -> None:
        """安全执行异步回调"""
        try:
            await callback(data)
        except Exception:
            logging.getLogger("OneBotHttpServer").exception(
                "回调执行错误: %s", callback
            )

    async def send(self, data: dict, with_echo: bool = False) -> dict | None:
        """HTTP 模式下 send 应由 OneBotSendClient 的 HTTP POST 完成

        Args:
            data: 发送数据
            with_echo: 是否等待回显

        Returns:
            None(HTTP 连接不处理直接发送）
        """
        self.log.warning(
            "OneBotHttpServer.send() 不应直接调用，请使用 OneBotSendClient"
        )
        return None

    async def close(self) -> None:
        """优雅关闭 HTTP 服务器"""
        self._running = False
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
            self._uvicorn_server = None
        self._listeners.clear()
        self.log.info("HTTP 服务器已关闭")

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
