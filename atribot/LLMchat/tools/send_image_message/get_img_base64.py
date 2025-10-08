from typing import List
import urllib.parse
import aiohttp
import random
import base64


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
    
    params = {
        "width": width,
        "height": height,
        "model": model,
        "nologo": str(nologo).lower(),
        "private": str(private).lower(),
        "enhance": str(enhance).lower(),
        "safe": str(safe).lower(),
        "Token": "56zs_9uGTfe19hUH"
    }
    
    if seed is not None:
        params["seed"] = random.randint(1, 1000)
    if image_url:
        params["image"] = image_url
    if referrer:
        params["referrer"] = referrer
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=timeout) as response:
                response.raise_for_status()  # 检查状态码
                
                return base64.b64encode(await response.read()).decode('utf-8')
                
    except aiohttp.ClientError as e:
        raise aiohttp.ClientError(f"网络请求错误: {e}")
    except Exception as e:
        raise Exception(f"图片生成失败: {e}")


# if __name__ == "__main__":
#     import asyncio
#     from pprint import pp
#     pp(asyncio.run(generate_image_base64(prompt="a cat riding a bicycle", width=512, height=512)))