from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.RAG.text_chunker import RecursiveCharacterTextSplitter
from atribot.LLMchat.RAG.vector_store import VectorStore
from atribot.core.service_container import container
# from atribot.common import common
from typing import List



class RAGManager:
    
    def __init__(self):
        self.config = container.get("config")
        self.supplier: ai_connection_manager = container.get("LLMSupplier")
        self.embedding_model = self.config.model.RAG.use_embedding_model.model_name
        self.embedding_api:universal_ai_api = self.supplier.get_filtration_connection(
            supplier_name = self.config.model.RAG.use_embedding_model.supplier
        )
        self.text_chunker = RecursiveCharacterTextSplitter(
            200,50
        )
        self.vector_store = VectorStore()
        
    
    def generate_response(self, question:str, context:str)->str:
        """发起一次请求

        Args:
            question (str): 问题
            context (str): 上下文

        Returns:
            str: 回复
        """
        
    
    def Split_text(self, text:str)->list[str]:
        """长文本按照规则分割成文本块

        Args:
            text (str): 文本

        Returns:
            list[str]: 分割后的文本块列表
        """
        return self.text_chunker.split_text(text)
        
        
        
    async def calculate_embedding(self, document:str|List[str])->list[list[float]]:
        """用嵌入式模型把文本转换成向量

        Args:
            document (str|List[str]): 要转换成向量的文本,或是要批量转换的文本列表

        Returns:
            list[list[float]]: 包含向量的列表
        """
        return await self.embedding_api.generate_embedding_vector(
            model=self.embedding_model,
            input=document,
            dimensions=1024,
            encoding="float"
        )
        
    def calculate_reranker(self, chunks:list[str], question:str, k:int=2)->list[str]:
        """根据问题对文本块列表进行相关性重排序，并返回得分最高的前 K 个文本块。

        Args:
            chunks (list[str]): 候选文本块列表。
                这些文本块通常由一个快速但精度不高的检索器
                初步筛选得出，它们是与问题可能相关的候选答案。
            question (str): 用户提出的问题或查询语句。
                重排序模型将以此问题为基准，来评估每个文本块的相关性。
            k (int, optional): 需要返回的、相关性最高的文本块数量。默认为 `2`。
                `k` 的值不应大于 `chunks` 列表的长度。

        Returns:
            list[str]: 一个包含相关性最高的前 K 个文本块的新列表。
                列表中的文本块已按相关性评分从高到低排序。
                如果 `k` 大于 `chunks` 的长度，则返回所有排序后的文本块。
                如果输入的 `chunks` 列表为空，则返回一个空列表。
        """
        
    async def search(self, embeddings:list[float], k:int=2)->tuple[dict]:
        """
        搜索与查询最相似的前 k 个文本块向量的文本块的和

        Args:
            embeddings (list): 每个文本块对应的嵌入向量列表。
            k (int, 可选): 每个向量要返回的最相似文本块的数量，默认为 2。

        Returns:
            combined_chunks (List[dict]): 前 k 个最相似文本块,结果合并后的列表行对象
        """
        sql = """
        SELECT 
            event
        FROM atri_memory
        WHERE event_vector <=> $1::vector(1024) <= 0.5
        ORDER BY event_vector <=> $1::vector(1024) ASC
        LIMIT $2
        """
        return_text = []
        async with self.vector_store.vector_database as db:
            for embedding in embeddings:
                return_text += await db.execute_with_pool(
                    sql = sql,
                    params = (embedding,k)
                )
                
        return tuple(return_text)
        
        
    async def store_memory(self, document:str):
        """对文本进行处理然后存储到数据库作为知识库记忆供查询

        Args:
            document (str): 要存储在向量数据库的记忆
        """
        text_list = self.Split_text(document)
        await self.vector_store.add_to_knowledge_base(
            text_list = text_list,
            embedding_list = await self.calculate_embedding(text_list)
        )



# if __name__ == "__main__":
#     print(RAGManager.fixed_size_chunking("abcdefghijklmnopqrsg",3,2))