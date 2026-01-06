from typing import List, Optional, Union
import urllib.parse
import asyncio
import aiohttp
import random
import base64

class pictureProcessing:
    
    API_TOKEN = "sk_UqXz8BbTGFwO8YRfpfDdleZoBJxRopJp"
    
    HEADERS = {
        "Authorization": f"Bearer {API_TOKEN}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    
    def __init__(self):
        self.step_lock = asyncio.Lock()
        
    async def step(self, message_data: dict[str, dict], prompt: str, model:str = "nanobanana") -> str:
        """图片处理主函数"""
        if self.step_lock.locked():
            raise RuntimeError("系统繁忙，请稍后再试")
        
        image_url_list: List[str] = []
        
        if message_data["message"][0]["type"] == "reply":
            from atribot.core.network_connections.qq_send_message import qq_send_message
            from atribot.core.service_container import container
            send_message: qq_send_message = container.get("SendMessage")
            reply_data = (await send_message.get_msg_details(message_data["message"][0]["data"]["id"]))["data"]
            for reply_message in reply_data["message"]:
                if reply_message.get("type") == "image":
                    image_url_list.append(reply_message["data"]["url"])
        
        for message in message_data["message"]:
            if message.get("type") == "image":
                image_url_list.append(message["data"]["url"])
        
        params = {
            "model": model, 
            "seed": random.randint(1, 1000),
            "nologo": "true",
        }
        
        if image_url_list:
            params["image"] = image_url_list[0]
        
        url = f"https://gen.pollinations.ai/image/{urllib.parse.quote(prompt)}"

        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            for attempt in range(3):
                try:
                    async with session.get(url, params=params, timeout=20) as response:
                        if response.status >= 500 and attempt < 2:
                            await asyncio.sleep(1)
                            continue
                        
                        response.raise_for_status()
                        return base64.b64encode(await response.read()).decode('utf-8')
                        
                except aiohttp.ClientError as e:
                    if attempt == 2:
                        raise aiohttp.ClientError(f"网络请求错误: {e}")
                except Exception as e:
                    if attempt == 2:
                        raise Exception(f"图片生成失败: {e}")

    @classmethod
    async def generate_image_base64(
        cls,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: str = "gptimage",
        image_url: Union[str, List[str], None] = None,
        nologo: bool = True,
        private: bool = False,
        enhance: bool = False,
        safe: bool = False,
        referrer: Optional[str] = None,
        timeout: int = 30
    ) -> str:
        """
        使用 Pollinations AI 生成图片并返回 Base64 编码
        
        Args:
            prompt: 图片描述文字
            width: 图片宽度（像素）
            height: 图片高度（像素）
            seed: 随机种子（可选）
            model: 生成模型，默认为 'gptimage'
            image_url: 输入图片URL（用于图生图）
            nologo: 是否禁用水印
            private: 是否私有模式
            enhance: 是否增强提示词
            safe: 是否启用安全过滤
            referrer: 来源标识符
            timeout: 请求超时时间（秒）
        
        Returns:
            str: 图片的 Base64 编码字符串
        
        Raises:
            aiohttp.ClientError: 网络请求错误
            Exception: API 返回错误
        """
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://gen.pollinations.ai/image/{encoded_prompt}"
        
        params = {
            "width": width,
            "height": height,
            "model": model,
            "nologo": str(nologo).lower(),
            "private": str(private).lower(),
            "enhance": str(enhance).lower(),
            "safe": str(safe).lower(),
        }
        
        if seed is not None:
            params["seed"] = seed
        else:
            params["seed"] = random.randint(1, 1000)

        if image_url:
            img_param = image_url[0] if isinstance(image_url, list) and image_url else image_url
            if isinstance(img_param, str):
                params["image"] = img_param
                
        if referrer:
            params["referrer"] = referrer
    
        last_exception = None
        
        async with aiohttp.ClientSession(headers=cls.HEADERS) as session:
            for _ in range(3):
                try:
                    async with session.get(url, params=params, timeout=timeout) as response:
                        response.raise_for_status()
                        return base64.b64encode(await response.read()).decode('utf-8')
                        
                except (aiohttp.ClientError, Exception) as e:
                    last_exception = e
                    await asyncio.sleep(0.5)

        if isinstance(last_exception, aiohttp.ClientError):
            raise aiohttp.ClientError(f"网络请求失败: {last_exception}")
        else:
            raise Exception(f"图片生成失败: {last_exception}")