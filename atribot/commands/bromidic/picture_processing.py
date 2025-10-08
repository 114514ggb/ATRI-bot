from typing import List
import urllib.parse
import asyncio
import aiohttp
import random
import base64


class pictureProcessing:
    
    def __init__(self):
        self.step_lock = asyncio.Lock()
        
    
    async def step(self,message_data: dict[str,dict], prompt:str)-> str:
        """图片处理主函数

        Args:
            message_data (dict): cq码消息体
            prompt (str): 图片prompt

        Raises:
            aiohttp.ClientError: _description_
            Exception: _description_

        Returns:
            base64(str): 返回图像的Base64编码
        """
        if self.step_lock.locked():
            raise RuntimeError("系统繁忙，请稍后再试。")
        
        image_url_list:List[str] = []
        
        if message_data["message"][0]["type"] == "reply":
            from atribot.core.network_connections.qq_send_message import qq_send_message
            from atribot.core.service_container import container
            send_message:qq_send_message = container.get("SendMessage")
            reply_data = (await send_message.get_msg_details(message_data["message"][0]["data"]["id"]))["data"]
            for reply_message in reply_data["message"]:
                if reply_message.get("type") == "image":
                    image_url_list.append(reply_message["data"]["url"])
        
        for message in message_data["message"]:
            if message.get("type") == "image":
                image_url_list.append(message["data"]["url"])
        
        params = {
            "model": "nanobanana",
            "seed": random.randint(1, 1000),
            "nologo": "true",
            "token": "56zs_9uGTfe19hUH"
        }
        
        if image_url_list:
            params["image"] = image_url_list[0]
            #还没支持多图片先将就一下
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}", 
                        params=params, 
                        timeout=20
                    ) as response:
                    response.raise_for_status()  # 检查状态码
                    
                    return base64.b64encode(await response.read()).decode('utf-8')
                    
        except aiohttp.ClientError as e:
            raise aiohttp.ClientError(f"网络请求错误: {e}")
        except Exception as e:
            raise Exception(f"图片生成失败: {e}")

    
    @staticmethod
    async def generate_image_base64(
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: int = None,
        model: str = "flux",
        image_url: str|List[str] = None,
        nologo: bool = True,
        private: bool = False,
        enhance: bool = False,
        safe: bool = False,
        referrer: str = None,
        timeout: int = 30
    ) -> str:
        """
        使用 Pollinations AI 生成图片并返回 Base64 编码
        
        Args:
            prompt: 图片描述文字
            width: 图片宽度（像素）
            height: 图片高度（像素）
            seed: 随机种子（可选）
            model: 生成模型，默认为 'flux'
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
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        
        headers = {
            'Authorization': 'Bearer 56zs_9uGTfe19hUH'
        }
        
        params = {
            "width": width,
            "height": height,
            "model": model,
            "nologo": str(nologo).lower(),
            "private": str(private).lower(),
            "enhance": str(enhance).lower(),
            "safe": str(safe).lower(),
            "token": "56zs_9uGTfe19hUH"
        }
        
        if seed is not None:
            params["seed"] = random.randint(1, 1000)
        if image_url:
            params["image"] = image_url
        if referrer:
            params["referrer"] = referrer
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout, headers=headers) as response:
                    response.raise_for_status()  # 检查状态码
                    
                    return base64.b64encode(await response.read()).decode('utf-8')
                    
        except aiohttp.ClientError as e:
            raise aiohttp.ClientError(f"网络请求错误: {e}")
        except Exception as e:
            raise Exception(f"图片生成失败: {e}")