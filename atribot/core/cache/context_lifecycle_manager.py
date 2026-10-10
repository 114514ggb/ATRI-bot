import json
import time
from logging import Logger
from typing import Any, Optional

from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.service_container import container
from atribot.core.type.context_types import Context


class ContextContainer:
    """用于参照的一个类"""
    
    user_id: int
    """user的qq号"""
    group_id:int
    """群号"""
    chat_context: Context
    """用于存储得上下文"""
    play_roles: str | None = None
    """当前人设名称"""
    last_msg_at: float
    """判断是否活跃的时间依据,应该是秒级别的time.monotonic()时间戳"""


class ContextLifecycleManager:
    """用于管理上下文冷热分离的"""
    
    def __init__(self, archival_after:float):
        self.log: Logger = container.get_by_type(Logger).getChild("Cache")
        self.database:AsyncPostgreSQL = container.get("database")
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
                play_roles = getattr(container_data, "play_roles", None)
                target_id = container_data.user_id if is_user_context else container_data.group_id
                
                success = False

                if is_user_context:
                    success = await self.save_user_context(target_id, messages, total_tokens, play_roles)
                else:
                    success = await self.save_group_context(target_id, messages, total_tokens, play_roles)
                
                if success:
                    if time.monotonic() - container_data.last_msg_at > self.archival_after:
                        keys_to_remove.append(key)
                        self.log.info(f"上下文归档成功: {'User' if is_user_context else 'Group'} {target_id}")
                    else:
                        self.log.info(f"归档期间 {'User' if is_user_context else 'Group'} {target_id} 变为活跃状态，跳过内存移除")
                else:
                    self.log.warning(f"上下文持久化失败: {'User' if is_user_context else 'Group'} {target_id}, 保留在内存中")

        for k in keys_to_remove:
            management_context_dict.pop(k, None)
    
    async def backup_data(self, management_context_dict: dict[int, ContextContainer], is_user_context: bool = True) -> dict[int, bool]:
        """对现有的上下文进行批量存储（只保存备份，不删除类里面的缓存）

        Args:
            management_context_dict (dict[int,ContextContainer]): 管理上下文的字典
            is_user_context (bool): 是否是user上下文

        Returns:
            dict[int, bool]: 每个 ID 对应的保存结果，True 表示成功，False 表示失败
        """
        contexts_to_save: list[tuple[int, list[dict[str, Any]], int, str | None]] = [
            (
                container_data.user_id if is_user_context else container_data.group_id,
                getattr(container_data.chat_context, "messages", []),
                getattr(container_data.chat_context, "total_tokens", 0),
                getattr(container_data, "play_roles", None)
            )
            for container_data in management_context_dict.values()
        ]
        
        if is_user_context:
            return await self.batch_save_user_contexts(contexts_to_save)
        else:
            return await self.batch_save_group_contexts(contexts_to_save)

    async def flush_all_contexts(
        self,
        group_context_dict: dict[int, ContextContainer],
        private_context_dict: dict[int, ContextContainer],
    ) -> None:
        """服务回收（关机）时的最终落盘

        先对群聊、私聊上下文各自执行一次全量备份写入数据库，无论备份成功与否
        最终都会清空两个内存字典，避免进程退出导致未归档的上下文丢失。

        备份与清空过程中出现的异常都会被捕获并记录日志，不会中断上层清理流程。

        Args:
            group_context_dict (dict[int, ContextContainer]): 群聊上下文管理字典
            private_context_dict (dict[int, ContextContainer]): 私聊上下文管理字典
        """
        group_total = len(group_context_dict)
        private_total = len(private_context_dict)

        if group_total == 0 and private_total == 0:
            self.log.debug("退出落盘：当前没有需要保存的上下文")
            return

        self.log.info(
            "退出落盘：开始保存群聊 %d 条、私聊 %d 条上下文", group_total, private_total
        )

        await self._flush_one_direction(
            group_context_dict, is_user_context=False, label="群聊"
        )
        await self._flush_one_direction(
            private_context_dict, is_user_context=True, label="私聊"
        )

    async def _flush_one_direction(
        self,
        management_context_dict: dict[int, ContextContainer],
        is_user_context: bool,
        label: str,
    ) -> None:
        """对单个方向的上下文做备份 + 清空，异常仅记录日志

        Args:
            management_context_dict (dict[int, ContextContainer]): 管理上下文的字典
            is_user_context (bool): 是否是user上下文
            label (str): 日志中使用的方向标签（如"群聊"/"私聊"）
        """
        if not management_context_dict:
            return

        try:
            results = await self.backup_data(
                management_context_dict=management_context_dict,
                is_user_context=is_user_context,
            )
            failed = [ctx_id for ctx_id, ok in results.items() if not ok]
            if failed:
                self.log.warning(
                    "退出落盘：%s 有 %d/%d 条保存失败（已保留在数据库原值），失败ID: %s",
                    label, len(failed), len(results), failed,
                )
            else:
                self.log.info("退出落盘：%s %d 条上下文保存成功", label, len(results))
        except Exception as e:
            self.log.error(
                "退出落盘：%s 上下文保存异常，仍将清空内存缓存: %s", label, e, exc_info=True
            )

        cleared = len(management_context_dict)
        management_context_dict.clear()
        self.log.info("退出落盘：已清空 %s 内存缓存 %d 条", label, cleared)
        
    
    async def save_user_context(
        self,
        user_id: int,
        context_data: list[dict[str, Any]],
        total_tokens: int,
        play_role: str | None = None
    ) -> bool:
        """保存用户私聊上下文到数据库。
        
        将用户的对话上下文以 JSONB 格式存储到 chat_context 表。如果该用户已存在记录，
        则更新现有数据；否则插入新记录。
        
        Args:
            user_id: 用户的唯一标识符。
            context_data: 包含对话消息的列表，每条消息为字典格式。
            total_tokens: 当前上下文的 token 总数，用于用量追踪。
            play_role: 当前人设名称，None 表示不修改该字段。
        
        Returns:
            bool: 保存成功返回 True，失败返回 False。
        """
        if play_role is None:
            sql = """
            INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, last_updated)
            VALUES ($1, NULL, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                context_data = EXCLUDED.context_data,
                total_tokens = EXCLUDED.total_tokens
            """
            params = (int(user_id), json.dumps(context_data), total_tokens)
        else:
            sql = """
            INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, play_role, last_updated)
            VALUES ($1, NULL, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                context_data = EXCLUDED.context_data,
                total_tokens = EXCLUDED.total_tokens,
                play_role = EXCLUDED.play_role
            """
            params = (int(user_id), json.dumps(context_data), total_tokens, play_role)
        
        try:
            async with self.database as db:
                await db.execute_with_pool(
                    query=sql,
                    params=params
                )
            return True
        except Exception as e:
            self.log.error(f"保存用户 {user_id} 上下文失败: {e}", exc_info=True)
            return False
    
    async def get_user_context(self, user_id: int) -> Optional[tuple[list[dict[str, Any]], str | None]]:
        """获取指定用户的私聊上下文。
        
        从数据库中检索用户的对话历史记录。
        
        Args:
            user_id: 要查询的用户的唯一标识符。
        
        Returns:
            Optional[tuple[list[dict[str, Any]], str | None]]: (上下文消息列表, 人设名称)，
                如果不存在则返回 None。
        """
        sql = """
        SELECT context_data, play_role
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
                    return json.loads(data[0]), data[1]
                return None
        except Exception as e:
            self.log.error(f"获取用户 {user_id} 上下文失败: {e}")
            return None
    
    async def save_group_context(
        self,
        group_id: int,
        context_data: list[dict[str, Any]],
        total_tokens: int,
        play_role: str | None = None
    ) -> bool:
        """保存群组聊天上下文到数据库。
        
        将群组的对话上下文以 JSONB 格式存储到 chat_context 表。如果该群组已存在记录，
        则更新现有数据；否则插入新记录。
        
        Args:
            group_id: 群组的唯一标识符。
            context_data: 包含群组对话消息的列表，每条消息为字典格式。
            total_tokens: 当前上下文的 token 总数，用于用量追踪。
            play_role: 当前人设名称，None 表示不修改该字段。
        
        Returns:
            bool: 保存成功返回 True，失败返回 False。
        """
        if play_role is None:
            sql = """
            INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, last_updated)
            VALUES (NULL, $1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (group_id) 
            DO UPDATE SET 
                context_data = EXCLUDED.context_data,
                total_tokens = EXCLUDED.total_tokens
            """
            params = (int(group_id), json.dumps(context_data), total_tokens)
        else:
            sql = """
            INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, play_role, last_updated)
            VALUES (NULL, $1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (group_id) 
            DO UPDATE SET 
                context_data = EXCLUDED.context_data,
                total_tokens = EXCLUDED.total_tokens,
                play_role = EXCLUDED.play_role
            """
            params = (int(group_id), json.dumps(context_data), total_tokens, play_role)
        
        try:
            async with self.database as db:
                await db.execute_with_pool(
                    query=sql,
                    params=params
                )
            return True
        except Exception as e:
            self.log.error(f"保存群组 {group_id} 上下文失败: {e}")
            return False
    
    async def get_group_context(self, group_id: int) -> Optional[tuple[list[dict[str, Any]], str | None]]:
        """获取指定群组的聊天上下文。
        
        从数据库中检索群组的对话历史记录。
        
        Args:
            group_id: 要查询的群组的唯一标识符。
        
        Returns:
            Optional[tuple[list[dict[str, Any]], str | None]]: (上下文消息列表, 人设名称)，
                如果不存在则返回 None。
        """
        sql = """
        SELECT context_data, play_role
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
                    return json.loads(data[0]), data[1]
                return None
        except Exception as e:
            self.log.error(f"获取群组 {group_id} 上下文失败: {e}")
            return None

    async def save_user_role(self, user_id: int, play_role: str) -> bool:
        """持久化用户的人设名称到 chat_context 表。

        仅更新 play_role 字段，不触碰 context_data / total_tokens。

        Args:
            user_id: 用户ID
            play_role: 人设名称

        Returns:
            bool: 保存成功返回 True，失败返回 False
        """
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, play_role, last_updated)
        VALUES ($1, NULL, '[]', $2, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            play_role = EXCLUDED.play_role
        """
        try:
            async with self.database as db:
                await db.execute_with_pool(
                    query=sql,
                    params=(int(user_id), play_role)
                )
            return True
        except Exception as e:
            self.log.error(f"保存用户 {user_id} 人设失败: {e}")
            return False

    async def save_group_role(self, group_id: int, play_role: str) -> bool:
        """持久化群组的人设名称到 chat_context 表。

        仅更新 play_role 字段，不触碰 context_data / total_tokens。

        Args:
            group_id: 群组ID
            play_role: 人设名称

        Returns:
            bool: 保存成功返回 True，失败返回 False
        """
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, play_role, last_updated)
        VALUES (NULL, $1, '[]', $2, CURRENT_TIMESTAMP)
        ON CONFLICT (group_id) 
        DO UPDATE SET 
            play_role = EXCLUDED.play_role
        """
        try:
            async with self.database as db:
                await db.execute_with_pool(
                    query=sql,
                    params=(int(group_id), play_role)
                )
            return True
        except Exception as e:
            self.log.error(f"保存群组 {group_id} 人设失败: {e}")
            return False

    async def batch_save_user_contexts(
        self,
        user_contexts: list[tuple[int, list[dict[str, Any]], int, str | None]]
    ) -> dict[int, bool]:
        """批量保存多个用户的私聊上下文到数据库。
        
        利用 executemany 高效批量插入/更新，单条失败不影响其他。
        
        Args:
            user_contexts: 用户上下文列表，每个元素为 (user_id, context_data, total_tokens, play_role) 的元组
        
        Returns:
            dict[int, bool]: 每个 user_id 对应的保存结果，True 表示成功，False 表示失败
        """
        if not user_contexts:
            return {}
        
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, play_role, last_updated)
        VALUES ($1, NULL, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            context_data = EXCLUDED.context_data,
            total_tokens = EXCLUDED.total_tokens,
            play_role = EXCLUDED.play_role
        """
        
        args_list = [
            (int(user_id), json.dumps(context_data), total_tokens, play_role)
            for user_id, context_data, total_tokens, play_role in user_contexts
        ]
        
        results = {}
        try:
            async with self.database as db:
                await db.executemany_with_pool(sql, args_list)
            for user_id, _, _, _ in user_contexts:
                results[user_id] = True
                # self.logger.debug(f"批量保存用户 {user_id} 上下文成功")
        except Exception as e:
            self.log.error(f"批量保存用户上下文失败: {e}")
            for user_id, context_data, total_tokens, play_role in user_contexts:
                try:
                    success = await self.save_user_context(user_id, context_data, total_tokens, play_role)
                    results[user_id] = success
                except Exception as inner_e:
                    self.log.error(f"单条保存用户 {user_id} 上下文失败: {inner_e}")
                    results[user_id] = False
        
        return results

    async def batch_save_group_contexts(
        self,
        group_contexts: list[tuple[int, list[dict[str, Any]], int, str | None]]
    ) -> dict[int, bool]:
        """批量保存多个群组的聊天上下文到数据库。
        
        利用 executemany 高效批量插入/更新，单条失败不影响其他。
        
        Args:
            group_contexts: 群组上下文列表，每个元素为 (group_id, context_data, total_tokens, play_role) 的元组
        
        Returns:
            dict[int, bool]: 每个 group_id 对应的保存结果，True 表示成功，False 表示失败
        """
        if not group_contexts:
            return {}
        
        sql = """
        INSERT INTO chat_context (user_id, group_id, context_data, total_tokens, play_role, last_updated)
        VALUES (NULL, $1, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT (group_id) 
        DO UPDATE SET 
            context_data = EXCLUDED.context_data,
            total_tokens = EXCLUDED.total_tokens,
            play_role = EXCLUDED.play_role
        """

        args_list = [
            (int(group_id), json.dumps(context_data), total_tokens, play_role)
            for group_id, context_data, total_tokens, play_role in group_contexts
        ]
        
        results = {}
        try:
            async with self.database as db:
                await db.executemany_with_pool(sql, args_list)
            for group_id, _, _, _ in group_contexts:
                results[group_id] = True
                # self.logger.debug(f"批量保存群组 {group_id} 上下文成功")
        except Exception as e:
            self.log.error(f"批量保存群组上下文失败: {e}")
            for group_id, context_data, total_tokens, play_role in group_contexts:
                try:
                    success = await self.save_group_context(group_id, context_data, total_tokens, play_role)
                    results[group_id] = success
                except Exception as inner_e:
                    self.log.error(f"单条保存群组 {group_id} 上下文失败: {inner_e}")
                    results[group_id] = False
        
        return results