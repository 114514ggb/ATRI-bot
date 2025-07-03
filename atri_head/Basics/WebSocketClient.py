# from concurrent.futures import ThreadPoolExecutor
from asyncio import Queue
import websockets
import asyncio
import json
import sys

class WebSocketClient:
    """WebSocket客户端类"""
    _instance = None
    maximum_retry = 1000
    """最大重连次数"""
    message_queue = Queue(10)
    """消息队列"""
    pending_requests_echos = {}
    """获取的回声列表"""

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WebSocketClient, cls).__new__(cls)
        return cls._instance

    def __init__(self, url = "127.0.0.1:8080",access_token = None, websocket=None):
        if not hasattr(self, "_initialized"):
            if access_token is None:
                self.uri = f'ws://{url}/'
            else:
                self.uri = f'ws://{url}/websocket?access_token={access_token}'
            self.websocket = websocket
            self._listeners = [
                self.add_pending_request
            ]
            self._running = False  # 控制循环的运行状态
            # self.executor = ThreadPoolExecutor(max_workers=4) # 以后可能会用到的线程池
            # self.loop = asyncio.get_event_loop()
            # self._lock = threading.Lock()
            self._initialized = True

    async def connect(self):
        """连接到WebSocket服务器"""
        while True:
            try:
                self.websocket = await websockets.connect(self.uri)
                print("NapCat连接成功!\n")
                self.maximum_retry = 10
                return self.websocket
            except Exception as e:
                if self.maximum_retry > 0:
                    self.maximum_retry -= 1
                    print(f"连接失败: {e}, 0.1秒后重试...")
                    await asyncio.sleep(0.1)
                else:
                    print(f"连接失败: {e}, 已达到最大重连次数")
                    sys.exit(1)

    async def start_while(self):
        """启动获取消息和处理消息的事件循环"""
        self._running = True
        try:
            await asyncio.gather(
                self.queue_put(), 
                self.queue_get(),
                return_exceptions=True
            )
        except Exception as e:
            print(f"事件循环意外终止: {e}")
        finally:
            self._running = False

    async def queue_put(self):
        while self._running:
            try:

                await self.message_queue.put(json.loads(await self.websocket.recv()))

            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
            except websockets.exceptions.ConnectionClosed as e:
                if e.code == 1005:
                    print("WebSocket连接正常关闭")
                else:
                    print(f"WebSocket连接异常关闭: {e}")
                    await self.connect()
            except Exception as e:
                print(f"未知错误: {e}")
                await self.connect()

    async def queue_get(self):
        while self._running:
            try:
                data = await self.message_queue.get()
                for callback in self._listeners:
                    try:
                        asyncio.create_task(callback(data))  # 异步回调
                        # callback(data)  # 同步回调
                        # await self.loop.run_in_executor(self.executor, callback, data) # 多线程异步回调
                    except Exception as e:
                        print(f"回调错误: {e}")
            except Exception as e:
                print(f"队列处理错误: {e}")
                
    async def close(self):
        """优雅关闭连接"""
        self._running = False  # 停止循环
        
        # 关闭WebSocket连接
        if self.websocket:
            await self.websocket.close()
            
        # 清空监听器和回声字典
        self._listeners.clear()
        self.pending_requests_echos.clear()
        
        # 清空消息队列
        while not self.message_queue.empty():
            await self.message_queue.get()
            
        asyncio.Task.cancel()
            
    def add_listener(self, callback):
        """添加消息监听器"""
        self._listeners.append(callback)
    
    async def add_pending_request(self, data):
        """添加待处理的回声"""
        # with self._lock:
        if "echo" in data and data["echo"] != "":
            # print("添加回声:",data["echo"])
            self.pending_requests_echos[data["echo"]] = data

    async def gain_echo(self,echo):
        """获取对应echo返回值"""
        for i in range(100):
            if echo in self.pending_requests_echos:

                echo_data = self.pending_requests_echos[echo]
                del self.pending_requests_echos[echo]
                # print("获取echo成功:",echo_data)
                return echo_data
            
            else:
                await asyncio.sleep(0.1)
        
        raise TimeoutError("获取echo超时")
