import numpy as np

class RAG_Manager:
    def __init__(self):
        pass
    
    def generate_response(self, question:str, context:str)->str:
        """发起一次请求

        Args:
            question (str): 问题
            context (str): 上下文

        Returns:
            str: 回复
        """
    
    def calculate_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
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
    
    def Split_text(self, text:str)->list[str]:
        """长文本按照规则分割成文本块

        Args:
            text (str): 文本

        Returns:
            list[str]: 分割后的文本块列表
        """
        
    def calculate_embedding(self, document:str)->list[float]:
        """用嵌入式模型把文本转换成向量

        Args:
            document (str): 要转换成向量的文本

        Returns:
            list[float]: 包含向量的列表
        """
        
    def calculate_reranker(self, chunks:list[str], question:str, k:int=1)->list[str]:
        """根据问题对文本块列表进行相关性重排序，并返回得分最高的前 K 个文本块。

        Args:
            chunks (list[str]): 候选文本块列表。
                这些文本块通常由一个快速但精度不高的检索器（如 BM25 或向量检索）
                初步筛选得出，它们是与问题可能相关的候选答案。
            question (str): 用户提出的问题或查询语句。
                重排序模型将以此问题为基准，来评估每个文本块的相关性。
            k (int, optional): 需要返回的、相关性最高的文本块数量。默认为 `1`。
                `k` 的值不应大于 `chunks` 列表的长度。

        Returns:
            list[str]: 一个包含相关性最高的前 K 个文本块的新列表。
                列表中的文本块已按相关性评分从高到低排序。
                如果 `k` 大于 `chunks` 的长度，则返回所有排序后的文本块。
                如果输入的 `chunks` 列表为空，则返回一个空列表。
        """
        
    def search(self, query:str, chunks:list[str], embeddings:list[float], k:int=1):
        """
        搜索与查询最相似的前 k 个文本块。

        Args:
            query (str): 查询字符串。
            chunks (list): 文本块列表。
            embeddings (list): 每个文本块对应的嵌入向量列表。
            k (int, 可选): 要返回的最相似文本块的数量，默认为 1。

        Returns:
            combined_chunks (str): 前 k 个最相似文本块合并后的文本。
        """
        
    def store_memory(self, document:str):
        """对文本进行处理然后存储到数据库供查询

        Args:
            document (str): 要存储在向量数据库的记忆
        """