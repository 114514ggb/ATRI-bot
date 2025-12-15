from asyncio import Queue, Event, create_task, gather, CancelledError, Task
from websockets.legacy.server import WebSocketServer as WSSercer, WebSocketServerProtocol, Serve
from typing import Optional, Dict, List, Callable, Any
from atribot.core.service_container import container
from websockets.datastructures import Headers
from urllib.parse import urlparse, parse_qs
from logging import Logger
import asyncio
import uuid
import json


class WebSocketServer:
    """WebSocket 服务端类（单例模式）"""
    
    _instance: Optional['WebSocketServer'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        access_token: Optional[str] = None,
        queue_size: int = 100,
        echo_timeout: float = 15.0
    ):
        """
        初始化 WebSocket 服务端
        
        Args:
            host: 监听地址
            port: 监听端口
            access_token: 访问令牌验证
            queue_size: 消息队列大小
            echo_timeout: Echo 响应超时时间（秒）
        """
        if hasattr(self, '_initialized'):
            return
        
        self.log: Logger = container.get("log")
        # self.log = logging.getLogger("WebSocketServer")
        
        # 服务器配置
        self.host = host
        self.port = port
        self.access_token = access_token
        
        # 运行状态
        self.websocket: Optional[WebSocketServerProtocol] = None
        """当前连接的客户端"""
        self._running = False
        """标志服务端启停"""
        self._connected = Event()
        """标志客户端是否已连接"""
        self._server = None
        """WebSocket 服务器实例"""
        
        # 消息处理
        self.message_queue: Queue = Queue(queue_size)
        self.pending_requests: Dict[str, asyncio.Future] = {}
        """存储要取得的回声dict"""
        self._listeners: List[Callable] = []
        
        # 任务管理
        self._tasks: List[Task] = []
        self.echo_timeout = echo_timeout
        
        self._initialized = True
    
    def _verify_token(self, path: str, headers:Headers) -> bool:
        """验证访问令牌"""
        if not self.access_token:
            return True
            
        if auth_header:= headers.get("Authorization"):
            parts = auth_header.split()
            
            if len(parts) == 2 and parts[0].lower() == "bearer":
                input_token = parts[1]
            else:
                input_token = auth_header
            
            self.log.debug(f"检测到Headers_Authorization参数认证信息: {input_token}")
            
            if input_token == self.access_token:
                return True

        query = urlparse(path).query
        params = parse_qs(query)
        token_list = params.get("access_token") or params.get("token")
        
        if token_list:
            input_token = token_list[0]
            self.log.debug(f"检测到 URL 参数认证信息: {input_token}")
            if input_token == self.access_token:
                return True
    
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
        self.log.info(f"NapCat 客户端已连接: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    if "echo" in data and data["echo"]:
                        echo_id = data["echo"]
                        if echo_id in self.pending_requests:
                            future = self.pending_requests.pop(echo_id)
                            if not future.done():
                                future.set_result(data)
                            continue
                    
                    await self.message_queue.put(data)
                    
                except json.JSONDecodeError as e:
                    self.log.error(f"JSON 解析错误: {e}")
                except Exception as e:
                    self.log.error(f"处理消息时发生错误: {e}")
        
        except Exception as e:
            self.log.error(f"连接处理异常: {e}")
        
        finally:
            # 连接断开
            if self.websocket == websocket:
                self.websocket = None
                self._connected.clear()
                self.log.info("NapCat 客户端已断开连接")
    
    async def start(self) -> None:
        """启动服务端"""
        if self._running:
            return
        
        self._running = True
        
        self._server: WSSercer = await Serve(
            self._handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10
        )
        
        self.log.info(f"WebSocket 服务器已启动: ws://{self.host}:{self.port}")
        
        self._tasks = [
            create_task(self._process_messages())
        ]
        
        try:
            await gather(*self._tasks, return_exceptions=False)
        except CancelledError:
            pass
        except Exception as e:
            self.log.critical(f"事件循环异常: {e}")
        finally:
            self._running = False
    
    async def _process_messages(self) -> None:
        """处理队列中的消息"""
        running_tasks = set()
        
        while self._running:
            try:
                data = await self.message_queue.get()
                
                for listener in self._listeners:
                    task = create_task(self._safe_callback(listener, data))
                    running_tasks.add(task)
                    task.add_done_callback(running_tasks.discard)
                    
            except Exception as e:
                self.log.error(f"处理消息时发生错误: {e}")
        
        if running_tasks:
            await gather(*running_tasks, return_exceptions=True)
    
    async def _safe_callback(self, callback: Callable, data: Dict) -> None:
        """安全执行异步回调函数"""
        try:
            await callback(data)
        except Exception as e:
            import traceback
            
            self.log.critical(
                "回调执行错误\n"
                "回调函数: %s\n"
                "异常类型: %s\n"
                "详细回溯:\n%s",
                callback,
                type(e).__name__,
                ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            )
    
    async def send(self, data: Dict, with_echo: bool = False) -> Optional[Dict]:
        """
        发送消息
        
        Args:
            data: 要发送的数据
            with_echo: 是否等待 echo 响应
            
        Returns:
            如果 with_echo=True，返回响应数据；否则返回 None
            
        Raises:
            ConnectionError: 客户端未连接
            TimeoutError: 等待响应超时
        """
        # if not self.websocket or not self.websocket.open:
        #     raise ConnectionError("客户端未连接")
        
        if with_echo:
            echo_id = self._generate_echo_id()
            data["echo"] = echo_id
            
            future = asyncio.get_event_loop().create_future()
            self.pending_requests[echo_id] = future
            
            try:
                await self.websocket.send(json.dumps(data))
                return await asyncio.wait_for(future, timeout=self.echo_timeout)
            except asyncio.TimeoutError:
                self.pending_requests.pop(echo_id, None)
                raise TimeoutError(f"等待 echo 响应超时 ({self.echo_timeout}秒)")
            except Exception as e:
                self.pending_requests.pop(echo_id, None)
                raise e
        else:
            await self.websocket.send(json.dumps(data))
            return None
    
    def _generate_echo_id(self) -> str:
        """生成唯一的 echo ID"""
        return str(uuid.uuid4())
    
    def add_listener(self, callback: Callable[[Dict], Any]) -> None:
        """
        添加消息监听器
        
        Args:
            callback: 回调函数，接收消息字典作为参数(必须是异步函数)
        """
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[Dict], Any]) -> None:
        """
        移除消息监听器
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """
        等待客户端连接
        
        Args:
            timeout: 超时时间（秒），None 表示无限等待
            
        Returns:
            是否成功连接
        """
        try:
            if timeout:
                await asyncio.wait_for(self._connected.wait(), timeout=timeout)
            else:
                await self._connected.wait()
            return True
        except asyncio.TimeoutError:
            return False
    
    @property
    def is_connected(self) -> bool:
        """检查客户端是否已连接"""
        return self.websocket is not None and self.websocket.open
    
    async def close(self) -> None:
        """优雅关闭服务器"""
        self._running = False
        self._connected.clear()
        
        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
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
        
        # 取消所有待处理的请求
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()
        
        # 清空消息队列
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        self.log.info("WebSocket 服务器已关闭")


# if __name__ == "__main__":
    
#     async def main():
#         WSSercer  = WebSocketServer(
#                 host= "127.0.0.1",
#                 port=8888,
#                 access_token= "ATRI114514"
#             )
        
#         async def _print(text):
#             print(text)
        
#         WSSercer.add_listener(_print)
#         await WSSercer.start()
#         await WSSercer.wait_for_connection()
        
#     asyncio.run(main())
    
     
# X-Self-ID: 3930909243
# Authorization: Bearer ATRI114514
# x-client-role: Universal
# User-Agent: OneBot/11
# Sec-WebSocket-Version: 13
# Sec-WebSocket-Key: CbDtm9hi6ujp5Nwl/eVncQ==
# Connection: Upgrade
# Upgrade: websocket
# Host: localhost:8888
