from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from atribot.core.service_container import container
from atribot.core.bot_types import Context
from typing import Any, Optional
from logging import Logger
import time
import json




class ContextContainer:
    
    user_id: int
    """user的qq号"""
    group_id:int
    """群号"""
    chat_context: Context
    """用于存储得上下文"""
    last_msg_at: float
    """判断是否活跃的时间依据,应该是秒级别的time.monotonic()时间戳"""


class ContextLifecycleManager:
    """用于管理上下文冷热分离的"""
    
    def __init__(self, archival_after:float):
        self.logger:Logger = container.get("log")
        self.database:atriAsyncPostgreSQL = container.get("database")
        self.archival_after: float = archival_after
        """归档的时间，超过这个时间不活跃的会被归档"""
    
    async def conduct_data_persistence(self, management_context_dict:dict[int,ContextContainer], is_user_context:bool = True) -> None:
        """检查然后对长时间没使用的上下文进行持久化
        如果是user会获取user_id存到user,不是的话就获取group_id存在group
        纯存储的是chat_context.messages这个列表,存储完成后又日志记录和对management_context_dict原有的进行移除

        Args:
            management_context_dict (dict[int,ContextContainer]): 管理上下文的字典
            is_user_context (bool): 是否是user上下文,
        """
        current_time = time.monotonic()
        keys_to_remove: list[int] = []

        for key, container_data in list(management_context_dict.items()):
            
            if current_time - container_data.last_msg_at > self.archival_after:
                
                context_obj = container_data.chat_context
                messages = getattr(context_obj, "messages", [])
                total_tokens = getattr(context_obj, "total_tokens", 0) 
                target_id = container_data.user_id if is_user_context else container_data.group_id
                
                success = False

                if is_user_context:
                    success = await self.save_user_context(target_id, messages, total_tokens)
                else:
                    success = await self.save_group_context(target_id, messages, total_tokens)
                
                if success:
                    if time.monotonic() - container_data.last_msg_at > self.archival_after:
                        keys_to_remove.append(key)
                        self.logger.info(f"上下文归档成功: {'User' if is_user_context else 'Group'} {target_id}")
                    else:
                        self.logger.info(f"归档期间 {'User' if is_user_context else 'Group'} {target_id} 变为活跃状态，跳过内存移除")
                else:
                    self.logger.warning(f"上下文持久化失败: {'User' if is_user_context else 'Group'} {target_id}, 保留在内存中")

        for k in keys_to_remove:
            management_context_dict.pop(k, None)
    
    async def backup_data(self, management_context_dict: dict[int, ContextContainer], is_user_context: bool = True) -> dict[int, bool]:
        """对现有的上下文进行批量存储（只保存，不删除）

        Args:
            management_context_dict (dict[int,ContextContainer]): 管理上下文的字典
            is_user_context (bool): 是否是user上下文

        Returns:
            dict[int, bool]: 每个 ID 对应的保存结果，True 表示成功，False 表示失败
        """
        contexts_to_save: list[tuple[int, list[dict[str, Any]], int]] = [
            (
                container_data.user_id if is_user_context else container_data.group_id,
                getattr(container_data.chat_context, "messages", []),
                getattr(container_data.chat_context, "total_tokens", 0)
            )
            for container_data in management_context_dict.values()
        ]
        
        if is_user_context:
            return await self.batch_save_user_contexts(contexts_to_save)
        else:
            return await self.batch_save_group_contexts(contexts_to_save)
        
    
    async def save_user_context(
        self,
        user_id: int,
        context_data: list[dict[str, Any]],
        total_tokens: int
    ) -> bool:
        """保存用户私聊上下文到数据库。
        
        将用户的对话上下文以 JSONB 格式存储到 chat_context 表。如果该用户已存在记录，
        则更新现有数据；否则插入新记录。
        
        Args:
            user_id: 用户的唯一标识符。
            context_data: 包含对话消息的列表，每条消息为字典格式。
            total_tokens: 当前上下文的 token 总数，用于用量追踪。
        
        Returns:
            bool: 保存成功返回 True，失败返回 False。
        """
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, last_updated)
        VALUES ($1, NULL, $2::jsonb, $3, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            context_data = EXCLUDED.context_data,
            total_tokens = EXCLUDED.total_tokens
        """
        
        try:
            async with self.database as db:
                await db.execute_with_pool(
                    query=sql,
                    params=(int(user_id), json.dumps(context_data), total_tokens)
                )
            return True
        except Exception as e:
            self.logger.error(f"保存用户 {user_id} 上下文失败: {e}")
            return False
    
    async def get_user_context(self, user_id: int) -> Optional[list[dict[str, Any]]]:
        """获取指定用户的私聊上下文。
        
        从数据库中检索用户的对话历史记录。
        
        Args:
            user_id: 要查询的用户的唯一标识符。
        
        Returns:
            Optional[list[dict[str, Any]]]: 用户的上下文消息列表，如果不存在则返回 None。
        """
        sql = """
        SELECT context_data
        FROM chat_context
        WHERE user_id = $1
        """
        
        try:
            async with self.database as db:
                if data := await db.execute_with_pool(
                    query=sql,
                    params=(int(user_id),),
                    fetch_type="one"
                ):
                    return json.loads(data[0])
                return None
        except Exception as e:
            self.logger.error(f"获取用户 {user_id} 上下文失败: {e}")
            return None
    
    async def save_group_context(
        self,
        group_id: int,
        context_data: list[dict[str, Any]],
        total_tokens: int
    ) -> bool:
        """保存群组聊天上下文到数据库。
        
        将群组的对话上下文以 JSONB 格式存储到 chat_context 表。如果该群组已存在记录，
        则更新现有数据；否则插入新记录。
        
        Args:
            group_id: 群组的唯一标识符。
            context_data: 包含群组对话消息的列表，每条消息为字典格式。
            total_tokens: 当前上下文的 token 总数，用于用量追踪。
        
        Returns:
            bool: 保存成功返回 True，失败返回 False。
        """
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, last_updated)
        VALUES (NULL, $1, $2::jsonb, $3, CURRENT_TIMESTAMP)
        ON CONFLICT (group_id) 
        DO UPDATE SET 
            context_data = EXCLUDED.context_data,
            total_tokens = EXCLUDED.total_tokens
        """
        
        try:
            async with self.database as db:
                await db.execute_with_pool(
                    query=sql,
                    params=(int(group_id), json.dumps(context_data), total_tokens)
                )
            return True
        except Exception as e:
            self.logger.error(f"保存群组 {group_id} 上下文失败: {e}")
            return False
    
    async def get_group_context(self, group_id: int) -> Optional[list[dict[str, Any]]]:
        """获取指定群组的聊天上下文。
        
        从数据库中检索群组的对话历史记录。
        
        Args:
            group_id: 要查询的群组的唯一标识符。
        
        Returns:
            Optional[list[dict[str, Any]]]: 群组的上下文消息列表，如果不存在则返回 None。
        """
        sql = """
        SELECT context_data
        FROM chat_context
        WHERE group_id = $1
        """
        
        try:
            async with self.database as db:
                if data := await db.execute_with_pool(
                    query=sql,
                    params=(int(group_id),),
                    fetch_type="one"
                ):
                    return json.loads(data[0])
                return None
        except Exception as e:
            self.logger.error(f"获取群组 {group_id} 上下文失败: {e}")
            return None

    async def batch_save_user_contexts(
        self,
        user_contexts: list[tuple[int, list[dict[str, Any]], int]]
    ) -> dict[int, bool]:
        """批量保存多个用户的私聊上下文到数据库。
        
        利用 executemany 高效批量插入/更新，单条失败不影响其他。
        
        Args:
            user_contexts: 用户上下文列表，每个元素为 (user_id, context_data, total_tokens) 的元组
        
        Returns:
            dict[int, bool]: 每个 user_id 对应的保存结果，True 表示成功，False 表示失败
        """
        if not user_contexts:
            return {}
        
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, last_updated)
        VALUES ($1, NULL, $2::jsonb, $3, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            context_data = EXCLUDED.context_data,
            total_tokens = EXCLUDED.total_tokens
        """
        
        args_list = [
            (int(user_id), json.dumps(context_data), total_tokens)
            for user_id, context_data, total_tokens in user_contexts
        ]
        
        results = {}
        try:
            async with self.database as db:
                await db.executemany_with_pool(sql, args_list)
            for user_id, _, _ in user_contexts:
                results[user_id] = True
                self.logger.debug(f"批量保存用户 {user_id} 上下文成功")
        except Exception as e:
            self.logger.error(f"批量保存用户上下文失败: {e}")
            for user_id, context_data, total_tokens in user_contexts:
                try:
                    success = await self.save_user_context(user_id, context_data, total_tokens)
                    results[user_id] = success
                except Exception as inner_e:
                    self.logger.error(f"单条保存用户 {user_id} 上下文失败: {inner_e}")
                    results[user_id] = False
        
        return results

    async def batch_save_group_contexts(
        self,
        group_contexts: list[tuple[int, list[dict[str, Any]], int]]
    ) -> dict[int, bool]:
        """批量保存多个群组的聊天上下文到数据库。
        
        利用 executemany 高效批量插入/更新，单条失败不影响其他。
        
        Args:
            group_contexts: 群组上下文列表，每个元素为 (group_id, context_data, total_tokens) 的元组
        
        Returns:
            dict[int, bool]: 每个 group_id 对应的保存结果，True 表示成功，False 表示失败
        """
        if not group_contexts:
            return {}
        
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, last_updated)
        VALUES (NULL, $1, $2::jsonb, $3, CURRENT_TIMESTAMP)
        ON CONFLICT (group_id) 
        DO UPDATE SET 
            context_data = EXCLUDED.context_data,
            total_tokens = EXCLUDED.total_tokens
        """

        args_list = [
            (int(group_id), json.dumps(context_data), total_tokens)
            for group_id, context_data, total_tokens in group_contexts
        ]
        
        results = {}
        try:
            async with self.database as db:
                await db.executemany_with_pool(sql, args_list)
            for group_id, _, _ in group_contexts:
                results[group_id] = True
                self.logger.debug(f"批量保存群组 {group_id} 上下文成功")
        except Exception as e:
            self.logger.error(f"批量保存群组上下文失败: {e}")
            for group_id, context_data, total_tokens in group_contexts:
                try:
                    success = await self.save_group_context(group_id, context_data, total_tokens)
                    results[group_id] = success
                except Exception as inner_e:
                    self.logger.error(f"单条保存群组 {group_id} 上下文失败: {inner_e}")
                    results[group_id] = False
        
        return results