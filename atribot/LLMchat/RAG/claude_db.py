import asyncio
from pymilvus import MilvusClient, AsyncMilvusClient, DataType

class AsyncMilvusManager:
    
    def __init__(
        self, 
        path: str = "http://localhost:19530", 
        token: str = "root:Milvus",
        collection_name: str = "atri_memory"
    ) -> None:
        """
        初始化 Milvus 管理器
        
        Args:
            uri: Milvus 服务器地址或是一个db文件的完整路径
            token: 认证令牌
            collection_name: 集合名称
        """
        self.client = MilvusClient(
            uri=path,
            token=token
        )

        self.async_client = AsyncMilvusClient(
            uri=path,
            token=token
        )
        self.collection_name = collection_name
    
    async def create_initial_collections(self):
        """
        初始化创建Collections(类似数据库表)
        注意：create_schema 和 has_collection 等方法目前不支持异步，使用同步客户端
        """

        if self.collection_name in self.client.list_collections():
            print(f"集合 {self.collection_name} 已存在,跳过创建.")
            return
        
        schema = self.client.create_schema(
            auto_id=True,
            enable_dynamic_field=False,
        )
        
        schema.add_field(field_name="memory_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="group_id", datatype=DataType.INT64)
        schema.add_field(field_name="user_id", datatype=DataType.INT64)
        schema.add_field(field_name="time", datatype=DataType.INT64)
        schema.add_field(field_name="event", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="event_vector", datatype=DataType.FLOAT_VECTOR, dim=1024)
        
        # 准备索引参数（同步操作）
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="event_vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 64}
        )
        
        # 创建集合（异步操作）
        await self.async_client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
            partition_key_field="group_id"
        )
        print(f"集合 {self.collection_name} 创建成功")

    async def add_data(self, data: list[dict], collection_name: str) -> list[int]:
        """向collection插入一条消息

        Args:
            data (list[dict]): 符合collection结构的数据列表
            collection_name (str): collection名称

        Returns:
            list[int]: 包含插入数据的主键的列表
        """

        res = await self.async_client.insert(
            collection_name=collection_name,
            data=data
        )
        return res["primary_keys"]

    async def add_memory(
        self,
        group_id: int,
        user_id: int,
        time: int,
        event: str,
        event_vector: list[float]
    ) -> list[int]:
        """向集合中添加新的记忆数据。

        该方法将群组信息、用户信息、时间戳、事件描述及其向量嵌入添加到Milvus集合中。
        数据会根据分区键(group_id)自动分配到相应的分区，提高查询效率。

        Args:
            group_id: 所属群组的唯一标识符
            user_id: 用户的唯一标识符
            time: 事件发生的时间戳（Unix时间戳）
            event: 事件描述的文本内容（最大长度1024字符）
            event_vector: 事件的向量表示（维度需与集合定义的dim一致）

        Returns:
            list[int]: 包含插入数据的主键(memory_id)的列表
        """
        return await self.add_data(
            data=[{
                "group_id": group_id,
                "user_id": user_id,
                "time": time,
                "event": event,
                "event_vector": event_vector
            }],
            collection_name=self.collection_name
        )

    async def inquire_data(
        self,
        query_vector: list[float],
        group_id: int,
        user_id: int = None,
        top_k: int = 5,
        min_similarity: float = 0.6
    ) -> list[dict]:
        """在指定群组中查询相似记忆。

        基于余弦相似度在特定群组分区内搜索与查询向量最接近的记忆事件。
        可选项按用户ID过滤，并设置相似度阈值和返回结果数量。

        Args:
            query_vector: 查询事件的向量表示
            group_id: 要搜索的群组ID（分区键）
            user_id: 可选过滤的用户ID（默认None表示不过滤）
            top_k: 返回的最相似结果数量（默认5）
            min_similarity: 最小相似度阈值（0.0-1.0，默认0.6）

        Returns:
            list[dict]: 包含记忆数据的字典列表，每个字典包含：
                - "id": 记忆项的唯一ID
                - "distance": 与查询向量的余弦相似度距离
                - "entity": 包含完整记忆数据的字典
        """
        # 构建过滤条件
        filter_expr = f"group_id == {group_id}"
        if user_id is not None:
            filter_expr += f" and user_id == {user_id}"
        
        # 执行异步向量相似度搜索
        res = await self.async_client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            filter=filter_expr,
            limit=top_k,
            output_fields=["memory_id", "group_id", "user_id", "time", "event"]
        )
        
        # 过滤并格式化结果（将距离转换为相似度分数）
        formatted_results = []
        for hit in res[0]:  # 因为只查询了一个向量
            # 将余弦距离转换为余弦相似度: similarity = 1 - distance
            similarity = 1 - hit["distance"]
            if similarity >= min_similarity:
                hit["entity"]["similarity"] = similarity
                formatted_results.append({
                    "id": hit["id"],
                    "distance": hit["distance"],
                    "entity": hit["entity"]
                })
        return formatted_results

    async def update_data(
        self, 
        memory_id: int, 
        new_event: str = None, 
        new_time: int = None,
        new_vector: list[float] = None
    ) -> bool:
        """更新指定记忆条目的内容。

        通过主键(memory_id)定位并更新记忆数据。支持更新事件描述、
        时间戳和向量表示中的一个或多个字段。

        Args:
            memory_id: 要更新的记忆项主键
            new_event: 新的事件描述文本（可选）
            new_time: 新的时间戳（可选）
            new_vector: 新的向量表示（可选）

        Returns:
            bool: 更新成功返回True，失败返回False

        Raises:
            ValueError: 当未提供任何更新字段时
        """
        if not any([new_event, new_time, new_vector]):
            raise ValueError("必须提供至少一个更新字段")
        
        # 构建更新数据
        update_data = {"memory_id": memory_id}  # 包含主键
        if new_event is not None:
            update_data["event"] = new_event
        if new_time is not None:
            update_data["time"] = new_time
        if new_vector is not None:
            update_data["event_vector"] = new_vector
        
        # 执行异步更新操作
        result = await self.async_client.upsert(
            collection_name=self.collection_name,
            data=[update_data]  # upsert 需要数据列表
        )
        return result["upsert_count"] > 0

    async def delete_memory(self, memory_id: int) -> bool:
        """删除指定的记忆条目。

        Args:
            memory_id: 要删除的记忆项主键

        Returns:
            bool: 删除成功返回True，失败返回False
        """
        result = await self.async_client.delete(
            collection_name=self.collection_name,
            filter=f"memory_id == {memory_id}"
        )
        return result["delete_count"] > 0

    async def query_memories_by_filter(
        self,
        filter_expr: str,
        output_fields: list[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """根据过滤条件查询记忆数据。

        Args:
            filter_expr: 过滤表达式
            output_fields: 要返回的字段列表
            limit: 返回结果的最大数量

        Returns:
            list[dict]: 查询结果列表
        """
        if output_fields is None:
            output_fields = ["memory_id", "group_id", "user_id", "time", "event"]
        
        result = await self.async_client.query(
            collection_name=self.collection_name,
            filter=filter_expr,
            output_fields=output_fields,
            limit=limit
        )
        return result

    async def load_collection(self):
        """加载集合到内存中以进行搜索。"""
        await self.async_client.load_collection(self.collection_name)
        print(f"集合 {self.collection_name} 已加载到内存")

    async def release_collection(self):
        """从内存中释放集合。"""
        await self.async_client.release_collection(self.collection_name)
        print(f"集合 {self.collection_name} 已从内存中释放")

    async def get_collection_stats(self) -> dict:
        """获取集合统计信息。
        
        注意：get_collection_stats 方法可能不支持异步，使用同步客户端
        """
        return self.client.get_collection_stats(self.collection_name)

    async def close(self):
        """关闭异步客户端连接。"""
        await self.async_client.close()


# 使用示例
async def main():
    # 创建异步管理器实例
    manager = AsyncMilvusManager(
        path="./milvus_atri.db"
    )
    
    try:
        # 初始化集合
        await manager.create_initial_collections()
        
        # 加载集合
        await manager.load_collection()
        
        # 添加记忆数据
        vector = [0.1] * 1024  # 示例向量
        memory_ids = await manager.add_memory(
            group_id=1,
            user_id=123,
            time=1234567890,
            event="这是一个测试事件",
            event_vector=vector
        )
        print(f"添加记忆成功，ID: {memory_ids}")
        
        # 查询相似记忆
        query_vector = [0.1] * 1024
        results = await manager.inquire_data(
            query_vector=query_vector,
            group_id=1,
            top_k=5
        )
        print(f"查询结果: {results}")
        
        # 更新记忆
        if memory_ids:
            success = await manager.update_data(
                memory_id=memory_ids[0],
                new_event="更新后的事件描述"
            )
            print(f"更新结果: {success}")
        
    finally:
        # 关闭连接
        await manager.close()

# 运行示例
if __name__ == "__main__":
    asyncio.run(main())
    # milvus_client = MilvusClient(uri="./milvus_demo.db")