from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from itertools import cycle
from typing import List
import aiohttp
import asyncio
import json


class ai_api_account_pool(universal_ai_api):
    """异步号池API"""
    
    def __init__(self, 
            api_key_pool:List[str] = None, 
            base_url:str = "https://api.deepseek.com/chat/completions", 
            tools = None
        ):
        
        self._headers_cycle = cycle(api_key_pool if api_key_pool else [])
        self.base_url = base_url
        
        if tools:
            self.tools = tools
        else:
            self.tools = []
        """模型可能会调用的 tool 的列表。最多支持 128 个 function。"""
        self.client:aiohttp.ClientSession|None = None
    
    async def _client_post(self,data:dict)->dict:
        max_retries = 3
        retry_delay = 0.3
        for attempt in range(max_retries):
            try:
                
                async with self.client.post(
                    self.base_url,
                    headers={'Authorization': f'Bearer {next(self._headers_cycle)}'},
                    data=data, 
                    # proxy='http://127.0.0.1:7890' # 代理
                ) as response:
                    try:
                        res_json = await response.json()
                        print(res_json)
                    except aiohttp.ContentTypeError:
                        res_json = json.loads(await response.text())
                        
                    if response.status != 200:
                        print(f"API Error {response.status}: {res_json}")
                        response.raise_for_status()
                        
                    return res_json
                
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
                timeout=aiohttp.ClientTimeout(total=120, connect=10), # 细分连接超时和总超时
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
            )
        return self