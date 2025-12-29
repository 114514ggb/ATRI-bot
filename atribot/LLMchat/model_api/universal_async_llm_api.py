from atribot.LLMchat.model_api.model_api_basics import model_api_basics
from typing import List
import aiohttp
import asyncio
import json


class universal_ai_api(model_api_basics):
    """通用异步AI API"""
    
    def __init__(self, 
            api_key = "sk-8403066c2841461491dd0b642a6c44af", 
            base_url = "https://api.deepseek.com/chat/completions", 
            tools = None
        ):
        super().__init__(api_key=api_key,base_url=base_url)
        
        self.headers = {
            'Content-Type': 'application/json',
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
                keepalive_timeout=10        # keepalive超时
            ),
            timeout=aiohttp.ClientTimeout(total=120),  # 总超时设置
            headers=self.headers
        )
        
    async def aclose(self):
        """异步关闭客户端"""
        await self.client.close()

    async def _client_post(self,data:dict)->dict:
        max_retries = 3
        retry_delay = 0.2
        for attempt in range(max_retries):
            try:

                async with self.client.post(
                    self.base_url,
                    # headers=self.headers,
                    data=data, 
                    # proxy='http://127.0.0.1:7890' # 代理
                ) as response:
                    try:
                        response_json:dict = await response.json()
                        print(response_json)
                    except aiohttp.ContentTypeError:
                        response_json = json.loads(await response.text())#fuck怎么会有字符串发过来?

                    if response.status != 200:
                        print(f"API Error {response.status}: {response_json}")
                        response.raise_for_status()
                    
                    return response_json
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    raise  e
                await asyncio.sleep(retry_delay)
    
    async def generate_text_tools(self, model:str, messages:list,tools:list):
        payload = json.dumps({
            "model": model,
            "messages": messages,
            'tools':tools,
            # 'response_format':response_format,
        } | self.model_parameters
        )
        
        for _ in range(3):
            try:
                ret = await self._client_post(payload)
                if ret["choices"]:#fuck None return
                    return ret
            except Exception:
                await asyncio.sleep(0.1)
                
        raise ValueError("LLMapi返回值错误!")

    async def generate_text_lightweight(self, model:str, messages:list):
        """请求生成文本,轻量参数,无工具调用,返回全部内容"""
        payload = json.dumps({
            "model": model,
            "messages": messages,
        })
        return await self._client_post(payload)
    
    async def generate_json_ample(self, model,remainder)->dict:
        payload = json.dumps({
            "model": model,
        }|remainder)
        
        # from pprint import pp
        # pp({
        #     "model": model,
        # }|remainder)
        # while True:
        for _ in range(3):
            try:
                ret = await self._client_post(payload)
                if ret['choices']:#fuck None return
                    return ret
            except Exception as e:
                print(e)
                await asyncio.sleep(0.1)
        
        raise ValueError("LLMapi返回值错误!")
    
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
        payload = json.dumps({
            "model" : model,
            "input" : input,
            "dimensions" : dimensions,
            "encoding_format" : encoding,
        })
        # ['embeddings']
        # ['embedding']
        return (await self._client_post(payload))['embeddings']
 
