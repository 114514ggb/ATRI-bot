from pymilvus import (
    AsyncMilvusClient, 
    DataType, 
    AnnSearchRequest, 
    WeightedRanker
)
from typing import List, Dict, Optional, Any

class MilvusManager:
    """Milvus 向量数据库异步管理类"""
    
    def __init__(
        self, 
        uri: str = "http://localhost:19530", 
        token: str = "root:Milvus",
        collection_name: str = "atri_memory"
    ) -> None:
        """
        初始化 Milvus 管理器
        
        Args:
            uri: Milvus 服务器地址
            token: 认证令牌
            collection_name: 集合名称
        """
        self.client = AsyncMilvusClient(uri=uri, token=token)
        self.collection_name = collection_name
        self.vector_dim = 1024  # 向量维度
    
    async def __aenter__(self):
        """支持异步上下文管理器"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时关闭连接"""
        await self.close()
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.close()
    
    async def create_collection(self, recreate: bool = False):
        """
        创建或重新创建集合
        
        Args:
            recreate: 如果集合已存在是否重新创建
        """
        if recreate and await self.has_collection():
            await self.client.drop_collection(self.collection_name)
            print(f"集合 {self.collection_name} 已删除")
        
        if not await self.has_collection():
            schema = self.client.create_schema(
                auto_id=True,
                enable_dynamic_field=False,
            )
            
            schema.add_field(field_name="memory_id", datatype=DataType.INT64, is_primary=True)
            schema.add_field(field_name="group_id", datatype=DataType.INT64)
            schema.add_field(field_name="user_id", datatype=DataType.INT64)
            schema.add_field(field_name="time", datatype=DataType.INT64)
            schema.add_field(field_name="event", datatype=DataType.VARCHAR, max_length=1024)
            schema.add_field(field_name="event_vector", datatype=DataType.FLOAT_VECTOR, dim=self.vector_dim)
            
            await self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                partition_key_field="group_id"
            )
            print(f"集合 {self.collection_name} 创建成功")
            
            await self.create_index()
        else:
            print(f"集合 {self.collection_name} 已存在，跳过创建")
    
    async def has_collection(self) -> bool:
        """检查集合是否存在"""
        collections = await self.client.list_collections()
        return self.collection_name in collections
    
    async def create_index(self):
        """为向量字段创建索引"""
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="event_vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 64}
        )
        
        await self.client.create_index(
            collection_name=self.collection_name,
            index_params=index_params
        )
        print(f"集合 {self.collection_name} 索引创建成功")
    
    async def load_collection(self):
        """加载集合到内存"""
        await self.client.load_collection(self.collection_name)
        print(f"集合 {self.collection_name} 已加载")
    
    async def release_collection(self):
        """从内存释放集合"""
        await self.client.release_collection(self.collection_name)
        print(f"集合 {self.collection_name} 已释放")
    
    async def add_memory(
        self,
        group_id: int,
        user_id: int,
        time: int,
        event: str,
        event_vector: List[float]
    ) -> List[int]:
        """
        向集合中添加新的记忆数据
        
        Args:
            group_id: 群组ID
            user_id: 用户ID
            time: 时间戳
            event: 事件描述
            event_vector: 事件向量
            
        Returns:
            插入数据的主键列表
        """
        if len(event_vector) != self.vector_dim:
            raise ValueError(f"向量维度应为 {self.vector_dim}, 实际为 {len(event_vector)}")
        
        data = [{
            "group_id": group_id,
            "user_id": user_id,
            "time": time,
            "event": event,
            "event_vector": event_vector
        }]
        
        res = await self.client.insert(
            collection_name=self.collection_name,
            data=data
        )
        
        return res["primary_keys"]
    
    async def search_memories(
        self,
        query_vector: List[float],
        group_id: int,
        user_id: Optional[int] = None,
        top_k: int = 5,
        min_similarity: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        搜索相似记忆
        
        Args:
            query_vector: 查询向量
            group_id: 群组ID
            user_id: 用户ID（可选）
            top_k: 返回结果数量
            min_similarity: 最小相似度阈值
            
        Returns:
            搜索结果列表，包含相似度和实体数据
        """
        # 构建过滤条件
        filter_expr = f"group_id == {group_id}"
        if user_id is not None:
            filter_expr += f" and user_id == {user_id}"
        
        # 执行向量搜索
        res = await self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            filter=filter_expr,
            limit=top_k,
            output_fields=["memory_id", "group_id", "user_id", "time", "event"],
            params={"ef": 32}  # HNSW 搜索参数
        )
        
        # 处理搜索结果
        results = []
        for hit in res[0]:
            similarity = 1 - hit["distance"]  # 将距离转换为相似度
            if similarity >= min_similarity:
                entity = hit["entity"]
                entity["similarity"] = round(similarity, 4)  # 保留4位小数
                results.append({
                    "id": hit["id"],
                    "similarity": similarity,
                    "entity": entity
                })
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results
    
    async def hybrid_search(
        self,
        dense_vector: List[float],
        sparse_vector: List[float],
        group_id: int,
        top_k: int = 5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        混合搜索（稠密向量 + 稀疏向量）
        
        Args:
            dense_vector: 稠密查询向量
            sparse_vector: 稀疏查询向量
            group_id: 群组ID
            top_k: 返回结果数量
            dense_weight: 稠密向量权重
            sparse_weight: 稀疏向量权重
            
        Returns:
            混合搜索结果列表
        """
        # 创建搜索请求
        dense_req = AnnSearchRequest(
            data=[dense_vector],
            anns_field="event_vector",
            param={"metric_type": "COSINE", "params": {"ef": 32}},
            limit=top_k
        )
        
        sparse_req = AnnSearchRequest(
            data=[sparse_vector],
            anns_field="event_vector",  # 假设有稀疏向量字段
            param={"metric_type": "IP"},
            limit=top_k
        )
        
        # 创建加权排序器
        ranker = WeightedRanker(dense_weight, sparse_weight)
        
        # 执行混合搜索
        res = await self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=ranker,
            limit=top_k,
            output_fields=["memory_id", "group_id", "user_id", "time", "event"]
        )
        
        # 处理搜索结果
        results = []
        for hit in res:
            entity = hit.entity
            entity["similarity"] = round(hit.distance, 4)
            results.append({
                "id": hit.id,
                "similarity": hit.distance,
                "entity": entity
            })
        
        return results
    
    async def update_memory(
        self, 
        memory_id: int, 
        new_event: Optional[str] = None, 
        new_time: Optional[int] = None,
        new_vector: Optional[List[float]] = None
    ) -> bool:
        """
        更新记忆条目
        
        Args:
            memory_id: 记忆ID
            new_event: 新事件描述
            new_time: 新时间戳
            new_vector: 新向量
            
        Returns:
            更新是否成功
        """
        if not any([new_event, new_time, new_vector]):
            raise ValueError("必须提供至少一个更新字段")
        
        # 构建更新数据
        update_data = {}
        if new_event is not None:
            update_data["event"] = new_event
        if new_time is not None:
            update_data["time"] = new_time
        if new_vector is not None:
            if len(new_vector) != self.vector_dim:
                raise ValueError(f"向量维度应为 {self.vector_dim}, 实际为 {len(new_vector)}")
            update_data["event_vector"] = new_vector
        
        # 执行更新
        res = await self.client.upsert(
            collection_name=self.collection_name,
            data=[{"memory_id": memory_id, **update_data}]
        )
        
        return res["upsert_count"] > 0
    
    async def delete_memory(self, memory_id: int) -> bool:
        """
        删除记忆条目
        
        Args:
            memory_id: 要删除的记忆ID
            
        Returns:
            删除是否成功
        """
        res = await self.client.delete(
            collection_name=self.collection_name,
            filter=f"memory_id == {memory_id}"
        )
        return res["delete_count"] > 0
    
    async def get_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个记忆条目
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆数据字典，如果不存在返回 None
        """
        res = await self.client.get(
            collection_name=self.collection_name,
            ids=[memory_id],
            output_fields=["memory_id", "group_id", "user_id", "time", "event"]
        )
        return res[0] if res else None
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            集合统计信息字典
        """
        return await self.client.describe_collection(self.collection_name)