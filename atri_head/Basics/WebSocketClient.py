import websockets,asyncio,json,sys
from concurrent.futures import ThreadPoolExecutor
from asyncio import Queue

class WebSocketClient:
    """WebSocket客户端类"""
    _instance = None
    maximum_retry = 10
    """最大重连次数"""
    message_queue = Queue(10)
    """消息队列"""
    pending_requests_echos = {}
    """获取的回声列表"""

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WebSocketClient, cls).__new__(cls)
        return cls._instance

    def __init__(self, uri = "127.0.0.1:8080",access_token = None, websocket=None):
        if not hasattr(self, "_initialized"):
            access_token = access_token
            if access_token is None:
                self.uri = f'ws://{uri}/'
            else:
                self.uri = f'ws://{uri}/websocket?access_token={access_token}'
            self.websocket = websocket
            self._listeners = [
                self.add_pending_request
            ]
            
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
                    print(f"连接失败: {e}, 10秒后重试...")
                    await asyncio.sleep(10)
                else:
                    print(f"连接失败: {e}, 已达到最大重连次数")
                    sys.exit(1)

    async def start_while(self):
        """启动获取消息和处理消息的事件循环"""
        await asyncio.gather(self.queue_put(), self.queue_get())

    async def queue_put(self):
        while True:
            try:

                await self.message_queue.put(json.loads(await self.websocket.recv()))

            except websockets.ConnectionClosed:
                print("连接断开，尝试重连...")
                await self.connect()

    async def queue_get(self):
        while True:
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
        for i in range(50):
            if echo in self.pending_requests_echos:

                echo_data = self.pending_requests_echos[echo]
                del self.pending_requests_echos[echo]
                # print("获取echo成功:",echo_data)
                return echo_data
            
            else:
                await asyncio.sleep(0.1)
        
        raise TimeoutError("获取echo超时")