import asyncio
import json
from itertools import cycle
from typing import AsyncGenerator, Dict, List

import aiohttp
from aiohttp.resolver import AsyncResolver

from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api


class ai_api_account_pool(universal_ai_api):
    """异步号池API"""
    
    def __init__(
        self, 
        api_key_pool:List[str] = None, 
        base_url:str = "https://api.deepseek.com/chat/completions", 
        tools = None
    ):
        super().__init__(base_url=base_url, tools=tools)
        
        self._headers_cycle = cycle(api_key_pool if api_key_pool else [])

        self.client:aiohttp.ClientSession|None = None
    
    async def _client_post(self,data:dict)->dict:
        max_retries = 3
        retry_delay = 0.5
        for attempt in range(max_retries):
            try:
                
                async with self.client.post(
                    self.base_url,
                    headers={'Authorization': f'Bearer {next(self._headers_cycle)}'},
                    json=data,
                    # proxy='http://127.0.0.1:7890' # 代理
                ) as response:
                    try:
                        # self.log.debug(await response.text()) # 调试用
                        response_json = await response.json()
                    except aiohttp.ContentTypeError:
                        response_json = json.loads(await response.text())

                    if response.status != 200:
                        self.log.warning(f"API Error {response.status}: {response_json}")
                        response.raise_for_status()
                        
                    return response_json
                
            except aiohttp.ClientResponseError as e:
                if 400 <= e.status < 500 and e.status != 429:
                    self.log.warning(f"client_post请求被拒绝(不重试): {e}")
                    raise
                self.log.warning(f"client_post内部请求(第 {attempt + 1} 次重试): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay * attempt)
            except Exception as e:
                self.log.warning(f"client_post内部请求(第 {attempt + 1} 次重试): {e}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(retry_delay * attempt)
                
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
                    keepalive_timeout=20,        # keepalive超时
                    resolver=AsyncResolver(
                        nameservers=['8.8.8.8', '8.8.4.4', '114.114.114.114'] #DNS相关
                    )
                ),
                timeout=aiohttp.ClientTimeout(total=180, connect=20), # 细分连接超时和总超时
                headers={
                    'Accept': 'application/json',
                }
            )
        return self
    
    async def client_post_stream(self, data: Dict) -> AsyncGenerator[Dict, None]:
        """
        底层流式请求方法,返回支持的Server-Sent Events (SSE) 协议包裹的 JSON 数据
        
        Args:
            data (Dict): 请求体参数
            
        Yields:
            Dict: 原始的 chunk json 数据
        """
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            has_yielded = False
            
            try:
                async with self.client.post(
                    self.base_url,
                    headers={'Authorization': f'Bearer {next(self._headers_cycle)}'},
                    # proxy='http://127.0.0.1:7890', # 代理
                    json=data
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        self.log.warning(f"Stream API Error (第 {attempt + 1} 次重试): {response.status} - {error_text}")
                        response.raise_for_status()
                        
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        
                        if not line or line.startswith(":"):
                            continue
                        
                        if line.startswith("data: "):
                            json_str = line[6:]
                            
                            if json_str == "[DONE]":
                                break
                            
                            try:
                                chunk_json = json.loads(json_str)
                                yield chunk_json
                                has_yielded = True
                            except json.JSONDecodeError:
                                self.log.warning(f"JSON解析失败: {json_str}")
                                continue          
                    return                 
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if has_yielded:
                    self.log.error(f"流式请求在传输中途中断: {e}。由于已传输部分数据，停止重试以防数据重复。")
                    raise e
                
                self.log.warning(f"流式请求连接错误 (第 {attempt + 1}/{max_retries} 次): {e}")
                
                if attempt == max_retries - 1:
                    raise e

                await asyncio.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                self.log.error(f"流式请求发生未知错误: {e}")
                raise e