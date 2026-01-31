from atribot.LLMchat.model_api.model_api_basics import model_api_basics
from atribot.LLMchat.model_api.stream_processor import StreamProcessor
from typing import List, Dict ,AsyncGenerator
import aiohttp
import asyncio
import json




class universal_ai_api(model_api_basics,StreamProcessor):
    """通用异步AI API"""
    
    def __init__(
        self, 
        api_key = "", 
        base_url = "https://api.deepseek.com/chat/completions", 
        tools = None
    ):
        super().__init__(api_key=api_key,base_url=base_url)
        
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        """请求头"""
        
        self.base_url = base_url
        if tools:
            self.tools = tools
        else:
            self.tools = []
        """模型可能会调用的 tool 的列表。最多支持 128 个 function。"""
        self.client = None
        
    @classmethod
    async def create(cls, api_key: str, base_url: str, tools: list = None):
        """推荐初始化的方法"""
        instance = cls(api_key=api_key, base_url=base_url, tools=tools)
        await instance.initialize()
        
        return instance
    
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
                keepalive_timeout=20        # keepalive超时
            ),
            timeout=aiohttp.ClientTimeout(total=360, connect=20),  # 总超时设置
            headers=self.headers
        )
        
    async def aclose(self):
        """异步关闭客户端"""
        await self.client.close()

    async def _client_post(self,data:Dict)->Dict:
        max_retries = 3
        retry_delay = 0.5
        for attempt in range(max_retries):
            try:
                async with self.client.post(
                    self.base_url,
                    json=data, 
                    # proxy='http://127.0.0.1:7890' # 代理
                ) as response:
                    try:
                        response_json: Dict = await response.json()
                        # print(response_json) # 调试用
                    except aiohttp.ContentTypeError:
                        # 处理返回头不是 application/json 但内容是 json 的情况
                        response_json = json.loads(await response.text())

                    if response.status != 200:
                        self.log.warning(f"API Error {response.status}: {response_json}")
                        response.raise_for_status()
                    
                    return response_json
                    
            except Exception as e:
                self.log.warning(f"client_post内部请求(第 {attempt + 1} 次重试): {e}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(retry_delay * attempt)
    
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
                    proxy='http://127.0.0.1:7890', # 代理
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
                    self.log.exception(f"流式请求在传输中途中断: {e}。由于已传输部分数据，停止重试以防数据重复。")
                    raise e
                
                self.log.warning(f"流式请求连接错误 (第 {attempt + 1}/{max_retries} 次): {e}")
                
                if attempt == max_retries - 1:
                    raise e

                await asyncio.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                self.log.exception(f"流式请求发生未知错误: {e}")
                raise e
    
    async def generate_text_tools(self, model:str, messages:list,tools:list):
        payload = {
            "model": model,
            "messages": messages,
            'tools':tools,
            # 'response_format':response_format,
            **self.model_parameters
        }
    
        max_retries = 3
        base_delay = 0.5
        
        for attempt in range(max_retries + 1):

            ret = await self._client_post(payload)
            
            if ret.get('choices'):#fuck None return
                return ret
            else:
                if attempt < max_retries:
                    sleep_time = base_delay * (2 ** attempt)
                    await asyncio.sleep(sleep_time)
                else:
                    raise ValueError(f"LLM API请求为空，已重试 {max_retries} 次")

    async def generate_text_lightweight(self, model:str, messages:list):
        """请求生成文本,轻量参数,无工具调用,返回全部内容"""
        payload = {
            "model": model,
            "messages": messages,
        }
        return await self._client_post(payload)
    
    async def generate_json_ample(self, model,remainder)->Dict:
        payload = {"model": model, **remainder}
        
        max_retries = 3
        base_delay = 0.5
        
        for attempt in range(max_retries + 1):

            ret = await self._client_post(payload)
                
            if ret.get('choices'):#fuck None return
                return ret
            else:
                if attempt < max_retries:
                    sleep_time = base_delay * (2 ** attempt)
                    await asyncio.sleep(sleep_time)
                else:
                    raise ValueError(f"LLM API请求为空，已重试 {max_retries} 次")
        
    
    async def generate_embedding_vector(self, model:str, input:list[str]|str, dimensions:int=1024, encoding:str = "float")->List[List[float]]:
        """异步调用指定的嵌入模型，将输入的文本转换为向量表示。

        Args:
            model (str): 要使用的嵌入模型的编码
            input (Union[str, List[str]]): 需要进行向量化的文本内容。可以是单个字符串，或一个字符串列表。
            dimensions (int): 输出向量的维度。默认为 1024
            encoding (str): 向量的编码格式。默认为 "float"。

        Returns:
            List[List[float]]: 返回的向量list,每一个字符串对应一个list
        """
        payload = {
            "model" : model,
            "input" : input,
            "dimensions" : dimensions,
            "encoding_format" : encoding,
        }
        
        ret = await self._client_post(payload)
        
        try:
            if embeddings := ret.get('embeddings'):
                return embeddings
            else:
                return [
                    embedding["embedding"]
                    for embedding in ret["data"]
                ]
        except Exception as e:
            self.log.exception(f"不兼容的嵌入返回值错误:{e}")

    async def generate_json_ample_stream(self, model: str, remainder: dict) -> dict:
        return await self.process_stream_simple(self.client_post_stream({"model": model, **remainder}))

