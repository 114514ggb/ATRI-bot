from typing import List
import numpy as np
import functools
import asyncio
import aiohttp
import base64
import time

"""
一些自己常用的方法
"""


class common():
    
    @staticmethod
    def is_qq(qq_id:str|int)->bool:
        """判断是否是qq号

        Args:
            qq_id (str | int): 要判断的

        Returns:
            bool: 是不是
        """
        qq_id = str(qq_id)
        if not qq_id.isdigit():
            return False
        return 5 <= len(qq_id) <= 11
    
    @staticmethod
    async def search_music(keywords, limit=5)->list[dict]:
        """
        网易云音乐搜索接口，返回歌曲信息列表
        
        Args:
            :keywords 搜索关键词
            :limit 返回数量
            
        Returns:
            歌曲名和id
            [{'name': '冬の花', 'id': 1345485069},...]
        """
        url = 'https://music.163.com/api/cloudsearch/pc'
        data = {'s': keywords, 'type': 1, 'limit': limit}
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://music.163.com/',
            'Accept': 'application/json, text/plain, */*'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as response:
                data = await response.json()
                # data = await response.text()
        # print(data)
        return [{"name":v["name"],"id":v["id"]}  for v in data['result'].get('songs',[])]
    
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """计算两个字符串之间的Levenshtein编辑距离
        
        使用空间优化的动态规划算法，计算将字符串s1转换为s2所需的最少
        单字符编辑操作次数（插入、删除、替换）。

        Args:
            s1 (str): 第一个字符串
            s2 (str): 第二个字符串

        Returns:
            int: 两个字符串之间的编辑距离
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = np.arange(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = np.zeros(len(s2) + 1, dtype=int)
            current_row[0] = i + 1
            
            for j, c2 in enumerate(s2):
                cost = min(
                    previous_row[j + 1] + 1,
                    current_row[j] + 1,
                    previous_row[j] + (1 if c1 != c2 else 0)
                )
                current_row[j + 1] = cost
            
            previous_row = current_row
        
        return previous_row[-1]

    @staticmethod
    def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
        """
        计算两个字符串之间的 Jaro-Winkler 相似度 (0.0 到 1.0)。
        
        Args:
            s1 (str): 第一个字符串。
            s2 (str): 第二个字符串。
            p (float): Winkler 调整中的前缀缩放因子，通常为 0.1。

        Returns:
            float: 介于 0.0 和 1.0 之间的 Jaro-Winkler 相似度分数。
        """
        if len(s1) > len(s2):
            s1, s2 = s2, s1

        len1, len2 = len(s1), len(s2)

        if len1 == 0:
            return 0.0

        match_distance = (len2 // 2) - 1
        
        s1_matches = [False] * len1
        s2_matches = [False] * len2
        
        m = 0
        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)
            
            for j in range(start, end):
                if s1[i] == s2[j] and not s2_matches[j]:
                    s1_matches[i] = True
                    s2_matches[j] = True
                    m += 1
                    break

        if m == 0:
            return 0.0

        t = 0
        k = 0
        for i in range(len1):
            if s1_matches[i]:
                while not s2_matches[k]:
                    k += 1
                if s1[i] != s2[k]:
                    t += 1
                k += 1
                
        jaro_sim = (m / len1 + m / len2 + (m - t // 2) / m) / 3.0

        common_prefix_len = 0
        for i in range(min(len1, 4)):
            if s1[i] == s2[i]:
                common_prefix_len += 1
            else:
                break
                
        return jaro_sim if common_prefix_len == 0 else jaro_sim + common_prefix_len * p * (1 - jaro_sim)
    
    @staticmethod
    def calculate_similarity(embedding1: list[float], embedding2: list[float]) -> float:
        """计算两个向量之间的余弦相似度。

        余弦相似度衡量的是两个向量在方向上的一致性，而忽略它们的大小。
        该值范围在 -1.0 到 1.0 之间。值越接近 1.0，表示两个向量越相似；
        值越接近 -1.0，表示两个向量越不相似；0.0 表示两者正交（无关）。
        这在自然语言处理中常用于比较词向量、句子向量或文档向量的语义相似性。

        Args:
            embedding1: 第一个向量，可以是一个列表或一个 NumPy 数组。
            embedding2: 第二个向量，可以是一个列表或一个 NumPy 数组。

        Returns:
            float: 两个输入向量之间的余弦相似度，是一个介于 -1.0 和 1.0 之间的浮点数。
        """
        return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
    
    @staticmethod
    def timer(func):
        """计算函数运行时间的装饰器（高精度）"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            
            run_time = end_time - start_time
            
            if run_time < 1e-6:
                time_str = f"{run_time * 1e9:.3f} ns"
            elif run_time < 1e-3:
                time_str = f"{run_time * 1e6:.3f} μs"
            elif run_time < 1:
                time_str = f"{run_time * 1e3:.3f} ms"
            else:
                time_str = f"{run_time:.6f} s"
            
            print(f"函数 {func.__name__} 运行时间: {time_str}")
            return result
        
        return wrapper
    
    @staticmethod
    async def urls_to_base64(urls: List[str], prefix:str="data:image/jpeg;base64,",concurrency: int = 5) -> List[str]:
        """
        并发下载一组图片 URL，返回对应的 base64 字符串列表。
        
        Args:
            urls: 图片地址列表
            concurrency: 最大并发量
            
        Returns:
            List[str]: 与输入顺序一致的 base64 字符串列表
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=concurrency * 2),
            headers={
                'User-Agent': 'QQ/9.9.21-39038 CFNetwork/1220.1 Darwin/20.3.0',
                'Accept': 'image/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            },
            timeout=aiohttp.ClientTimeout(total=20)
        ) as session:
            
            async def fetch(url: str) -> str:
                async with semaphore:
                    try:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                if len(content) == 0:
                                    return ""
                                return f"{prefix}{base64.b64encode(content).decode('utf-8')}"
                            else:
                                return ""
                    except Exception:
                        return ""
                
            return await asyncio.gather(*(fetch(u) for u in urls))

    @staticmethod
    def construction_message_dict(template: list[dict], url_prefix: str = "") -> list[dict]:
        """
        将包含image和text的字典转换为指定格式的消息列表（按原始键顺序）
        
        Args:
            template (dict): 包含"image"和/或"text"键的字典
            url_prefix (str): 图片文件路径的前缀,会统一加在所有前面\n
                本地路径:"file://D:/a.jpg"\n
                网络路径:"http://123456.com/a.jpg"\n
                base64编码:"base64://xxx"
                
        Returns:
            list[dict]: 转换后的消息字典列表
        
        Example:
            input: [{"image":"ATRI_思考.jpg"},{"text":"是思考啊"}]
            output: [
                {"type": "image", "data": {"file": "path/ATRI_思考.jpg"}},
                {"type": "text", "data": {"text": "是思考啊"}}
            ]
        """
        result = []
        
        for item in template:
            for key, value in item.items():
                if not value:
                    continue
                
                if key == "image":
                    image_path = url_prefix + value if url_prefix else value
                    result.append({
                        "type": "image",
                        "data": {
                            "file": image_path
                        }
                    })
                elif key == "text":
                    result.append({
                        "type": "text",
                        "data": {
                            "text": value
                        }
                    })
        
        return result

# if __name__ == "__main__":
#     from pprint import pp
#     import asyncio
#     pp(asyncio.run(common().urls_to_base64([
#         "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhRl36i0Ixf49SDmjaxVmdMR8yjTbxiy7gkg_wooi-CA6LqAkAMyBHByb2RQgL2jAVoQLpqJOxD9AwyKKIfSiRqTbnoCqTSCAQJneg&rkey=CAMSMBxmyRdldyYvmTxVpyDAQfvIrP8IrUvbXvIyLFWRP6UZ4-mTM3FdgweFUupCGBBeRg"
#     ])))