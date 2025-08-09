from pymilvus import MilvusClient,AsyncMilvusClient, DataType
import asyncio


class milvus_Manager:
    
    def __init__(
        self, 
        path:str="http://localhost:19530", 
        token:str="root:Milvus",
        collection_name: str = "atri_memory"
    )->None:
        self.client = MilvusClient(
            uri = path,
            token = token
        )
        self.async_client = AsyncMilvusClient(
            uri = path,
            token = token
        )
        self.collection_name = collection_name
        self.loop = asyncio.get_event_loop()
    
    async def create_initial_collections(self):
        """
        初始化创建Collections(类似数据库表)
        """
        def _create():
            if self.collection_name in self.client.list_collections():
                print(f"集合 {self.collection_name} 已存在,跳过创建.")
                return
            
            schema = MilvusClient.create_schema(
                auto_id=True,
                enable_dynamic_field=False,
            )
            
            schema.add_field(field_name="memory_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
            schema.add_field(field_name="group_id", datatype=DataType.INT64)
            schema.add_field(field_name="user_id", datatype=DataType.INT64)
            schema.add_field(field_name="time", datatype=DataType.INT64)
            schema.add_field(field_name="event", datatype=DataType.VARCHAR, max_length=1024)
            schema.add_field(field_name="event_vector", datatype=DataType.FLOAT_VECTOR, dim=1024)
            
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="event_vector",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 64}
            )
            
            self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params,
                partition_key_field="group_id"
            )
            print(f"集合 {self.collection_name} 创建成功")
        
        await self.run_in_thread(_create)

    async def add_data(self, data:list[dict], collection_name:str) -> list[int]:
        """向collection插入一条消息

        Args:
            data (list[dict]): 符合collection结构的数据列表
            collection_name (str): collection名称

        Returns:
            list[int]: 包含插入数据的主键的列表
        """
        # partition_name
        def _insert():
            res = self.client.insert(
                collection_name=collection_name,
                data=data
            )
            return res["primary_keys"]
        
        return await self.run_in_thread(_insert)

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
            data = [{
                "group_id": group_id,
                "user_id": user_id,
                "time": time,
                "event": event,
                "event_vector": event_vector
            }],
            collection_name = self.collection_name
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
        def _search():
            # 构建过滤条件
            filter_expr = f"group_id == {group_id}"
            if user_id is not None:
                filter_expr += f" and user_id == {user_id}"
            
            # 执行向量相似度搜索
            res = self.client.search(
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
        
        return await self.run_in_thread(_search)

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
        def _update():

            if not any([new_event, new_time, new_vector]):
                raise ValueError("必须提供至少一个更新字段")
            
            # 构建更新数据字典
            update_data = {}
            if new_event is not None:
                update_data["event"] = new_event
            if new_time is not None:
                update_data["time"] = new_time
            if new_vector is not None:
                update_data["event_vector"] = new_vector
            
            # 执行更新操作
            result = self.client.upsert(
                collection_name=self.collection_name,
                filter=f"memory_id == {memory_id}",
                updates=update_data
            )
            return result["update_count"] > 0
        
        return await self.run_in_thread(_update)
    
    async def run_in_thread(self, func):
        """在单独的线程中运行函数并返回结果"""
        return await self.loop.run_in_executor(None, func)