from typing import Optional, Dict, List, Callable, Any
from asyncio import Queue, Event, create_task, sleep, gather, CancelledError, Task
from atribot.core.service_container import container
from contextlib import asynccontextmanager
from logging import Logger
import websockets
import asyncio
import uuid
import json
import sys


class WebSocketClient:
    """WebSocket 客户端类（单例模式）"""
    
    _instance: Optional['WebSocketClient'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self, 
        url: str = "127.0.0.1:8080",
        access_token: Optional[str] = None,
        max_retries: int = 120,
        retry_delay: float = 1.0,
        queue_size: int = 100,
        echo_timeout: float = 15.0
    ):
        """
        初始化 WebSocket 客户端
        
        Args:
            url: WebSocket 服务器地址
            access_token: 访问令牌
            max_retries: 最大重连次数
            retry_delay: 重连延迟（秒）
            queue_size: 消息队列大小
            echo_timeout: Echo 响应超时时间（秒）
        """
        if hasattr(self, '_initialized'):
            return
        
        self.log:Logger =  container.get("log")
        
        # 连接配置
        self.url = url
        self.access_token = access_token
        self.uri = self._build_uri()
        
        # 重连配置
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._retry_count = 0
        
        # 运行状态
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        """标志客户端启停"""
        self._connected = Event()
        
        # 消息处理
        self.message_queue: Queue = Queue(queue_size)
        self.pending_requests: Dict[str, asyncio.Future] = {}
        """存储要取得的回声dict"""
        self._listeners: List[Callable] = []
        
        # 任务管理
        self._tasks: List[Task] = []
        self.echo_timeout = echo_timeout
        
        self._initialized = True
    
    def _build_uri(self) -> str:
        """构建 WebSocket URI"""
        protocol = "ws://"
        if self.access_token:
            return f"{protocol}{self.url}/websocket?access_token={self.access_token}"
        return f"{protocol}{self.url}/"
    
    async def connect(self) -> None:
        """连接到 WebSocket 服务器"""
        while self._retry_count < self.max_retries:
            try:
                self.websocket = await websockets.connect(
                    self.uri,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                self.log.info("NapCat 连接成功!")
                self._retry_count = 0
                self._connected.set()
                return
                
            except Exception as e:
                self._retry_count += 1
                self._connected.clear()
                
                if self._retry_count >= self.max_retries:
                    self.log.info(f"连接失败: {e}, 已达到最大重连次数 ({self.max_retries})")
                    sys.exit(1)
                
                self.log.critical(f"连接失败: {e}\n{self.retry_delay} 秒后重试... ({self._retry_count}/{self.max_retries})")
                await sleep(self.retry_delay)
    
    async def start(self) -> None:
        """启动客户端"""
        if self._running:
            return
            
        self._running = True
        await self.connect()
        
        # 创建并管理任务
        self._tasks = [
            create_task(self._receive_messages()),
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
    
    async def _receive_messages(self) -> None:
        """接收消息并放入队列"""
        while self._running:
            try:
                if not self.websocket:
                    await self._connected.wait()
                    continue
                
                data = json.loads(await self.websocket.recv())
                
                if "echo" in data and data["echo"]:
                    echo_id = data["echo"]
                    if echo_id in self.pending_requests:
                        future = self.pending_requests.pop(echo_id)
                        if not future.done():
                            future.set_result(data)
                    continue
                            
                # 防止队列满导致阻塞,移除最旧的消息
                # if self.message_queue.full():
                #     try:
                #         self.message_queue.get_nowait()
                #     except asyncio.QueueEmpty:
                #         pass
                                # 处理 echo 响应
                
                await self.message_queue.put(data)
                
            except json.JSONDecodeError as e:
                self.log.error(f"JSON 解析错误: {e}")
                
            except websockets.exceptions.ConnectionClosed as e:
                self._connected.clear()
                if e.code == 1005:
                    self.log.info("WebSocket 连接正常关闭")
                    if self._running:
                        await self.connect()
                else:
                    self.log.critical(f"WebSocket 连接异常关闭: {e}")
                    if self._running:
                        await self.connect()
                        
            except Exception as e:
                self.log.error(f"接收消息时发生错误: {e}")
                if self._running:
                    self._connected.clear()
                    await sleep(self.retry_delay)
                    await self.connect()
    
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
        """安全执行回调函数"""
        try:
            # if asyncio.iscoroutinefunction(callback):
                await callback(data)
            # else:
            #     await asyncio.get_event_loop().run_in_executor(None, callback, data)
        except Exception as e:
            import traceback
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))

            self.log.critical(
                "回调执行错误\n"
                "回调函数: %s\n"
                "异常类型: %s\n"
                "详细回溯:\n%s",
                callback,              # 函数对象
                type(e).__name__,      # 异常类型名
                tb_str                 # 带行号的完整栈
            )
    
    async def send(self, data: Dict, with_echo: bool = False) -> Optional[Dict]:
        """
        发送消息
        
        Args:
            data: 要发送的数据
            with_echo: 是否等待 echo 响应
            
        Returns:
            如果 with_echo=True，返回响应数据；否则返回 None
        """
        # if not self.websocket:
        #     await self._connected.wait()
        
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
            callback: 回调函数，接收消息字典作为参数(不要添加非异步函数)
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
    
    async def close(self) -> None:
        """优雅关闭连接"""
        self._running = False
        self._connected.clear()
        
        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
        if self._tasks:
            await gather(*self._tasks, return_exceptions=True)
        
        # 关闭 WebSocket 连接
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
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
    
    @asynccontextmanager
    async def session(self):
        """上下文管理器，自动管理连接生命周期"""
        try:
            await self.start()
            yield self
        finally:
            await self.close()
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.websocket is not None and not self.websocket.closed
    
    @property
    def is_running(self) -> bool:
        """检查客户端是否正在运行"""
        return self._running