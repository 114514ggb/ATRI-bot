from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from typing import List
import aiohttp
import asyncio
import json


class ai_api_account_pool(universal_ai_api):
    """通用异步AI API"""
    
    def __init__(self, 
            api_key_pool:List[str] = None, 
            base_url:str = "https://gateway.ai.cloudflare.com/v1/824184f590d653076279e09f520d4c41/atri/compat/v1/chat/completions", 
            tools = None
        ):
        
        self.account_pool = api_key_pool if api_key_pool else []
        self._lock = asyncio.Lock()
        self._current_index = 0
        self.base_url = base_url
        
        if tools:
            self.tools = tools
        else:
            self.tools = []
        """模型可能会调用的 tool 的列表。最多支持 128 个 function。"""
        self.client:aiohttp.ClientSession|None = None

    async def get_headers(self)->dict:
        """轮询获取一个账号的请求头

        Raises:
            ValueError: _api_key_pool 为空

        Returns:
            dict: 请求头
        """
        if not self.account_pool:
            raise ValueError("API key pool为空，请提供至少一个API key")
        async with self._lock:

            api_key = self.account_pool[self._current_index]
            
            self._current_index = (self._current_index + 1) % len(self.account_pool)
            
            return {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
    
    async def _client_post(self,data:dict)->dict:
        max_retries = 3
        retry_delay = 0.5
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    self.base_url,
                    headers=await self.get_headers(),
                    data=data,
                    # proxy='http://127.0.0.1:7890' # 代理
                )
                try:
                    response_json = await response.json()
                    print(response_json)
                    return response_json
                except aiohttp.ContentTypeError:
                    return json.loads(await response.text())
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise  e
                await asyncio.sleep(retry_delay)
                
    async def initialize(self):
        """
        异步初始化方法
        """
        if self.client is None:
            self.client = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=100,                  # 最大连接数
                limit_per_host=5,           # 单主机保持连接数
                force_close=False,          # 允许keepalive
                enable_cleanup_closed=True, # 自动清理关闭连接
                keepalive_timeout=10        # keepalive超时
            ),
            timeout=aiohttp.ClientTimeout(total=120),  # 总超时设置
        )