from atribot.core.db.atri_async_Database import AtriDB_Async
from atribot.core.service_container import container
from atribot.common import common

from typing import Set
import logging



class permissions_management:
    """
    异步权限管理类
    """
    PERM_LEVEL_ROOT = 3
    PERM_LEVEL_ADMIN = 2
    PERM_LEVEL_TOURIST = 1
    PERM_LEVEL_BLACKLIST = 0

    ROLE_ROOT = "root"
    ROLE_ADMIN = "administrator"
    ROLE_TOURIST = "tourist"
    ROLE_BLACKLIST = "blacklist"

    PERMISSION_MAP = {
        ROLE_ADMIN: 'administrator',
        ROLE_BLACKLIST: 'blacklist'
    }

    def __init__(self):
        self.db: AtriDB_Async = container.get("database")
        self.logging: logging.Logger = container.get("log")
        
        self.root: Set[int] = {2631018780} 
        self.administrator: Set[int] = set()
        self.blacklist: Set[int] = set()

    @classmethod
    async def create(cls):
        """
        异步创建并初始化权限管理实例。
        这是推荐的实例化方式，因为它会从数据库同步初始权限。
        """
        instance = cls()
        await instance.sync_from_db()
        return instance

    def _get_user_permission_level(self, user_id: int) -> int:
        """内部辅助方法：获取用户的权限等级"""
        if user_id in self.root:
            return self.PERM_LEVEL_ROOT
        if user_id in self.administrator:
            return self.PERM_LEVEL_ADMIN
        if user_id in self.blacklist:
            return self.PERM_LEVEL_BLACKLIST
        return self.PERM_LEVEL_TOURIST

    def _get_user_role(self, user_id: int) -> str:
        """获取用户的角色名称"""
        level = self._get_user_permission_level(user_id)
        if level == self.PERM_LEVEL_ROOT:
            return self.ROLE_ROOT
        if level == self.PERM_LEVEL_ADMIN:
            return self.ROLE_ADMIN
        if level == self.PERM_LEVEL_BLACKLIST:
            return self.ROLE_BLACKLIST
        return self.ROLE_TOURIST

    async def _modify_permission(self, target_user_id: int, operator_id: int, permission_role: str, required_level: int, action: str):
        """
        抽象通用方法来处理权限变更，并同步到数据库。
        
        Args:
            target_user_id (int): 目标用户ID
            operator_id (int): 操作者用户ID
            permission_role (str): 目标权限角色 (e.g., 'administrator', 'blacklist')
            required_level (int): 执行操作所需的最低权限等级
            action (str): 操作类型, 'add' 或 'remove'
            
        Raises:
            PermissionError: 当操作者权限不足时
            ValueError: 当用户ID不合法或操作无效时
        """
        operator_level = self._get_user_permission_level(operator_id)
        
        if operator_level < required_level:
            raise PermissionError("操作失败：您的权限不足。")

        if not common.is_qq(target_user_id):
            raise ValueError(f"无法操作：{target_user_id} 不是一个合法的QQ号。")
            
        target_role_name = self._get_user_role(target_user_id)
        target_list = getattr(self, permission_role, None)

        if target_list is None:
            raise ValueError(f"无效的权限角色: {permission_role}")

        if action == 'add':
            if target_role_name in [self.ROLE_ROOT, self.ROLE_ADMIN]:
                 raise ValueError(f"无法添加：用户 {target_user_id} 已经是管理员或更高权限。")
            if target_user_id in target_list:
                raise ValueError(f"无法添加：用户 {target_user_id} 已在该列表中。")
            
            await self._sync_to_db(target_user_id, permission_role, operator_id, 'add')
            
            target_list.add(target_user_id)
            
            self.logging.info(f"操作成功：用户 {target_user_id} 已被 {operator_id} 添加到 {permission_role} 列表。")

        elif action == 'remove':
            if target_user_id not in target_list:
                raise ValueError(f"无法删除：用户 {target_user_id} 不在该列表中。")

            await self._sync_to_db(target_user_id, permission_role, operator_id, 'remove')
            
            target_list.remove(target_user_id)
            
            self.logging.info(f"操作成功：用户 {target_user_id} 已被 {operator_id} 从 {permission_role} 列表移除。")
        else:
            raise ValueError("无效的操作类型。")

    async def add_administrator(self, user_id: int, operator_id: int):
        """添加管理员"""
        await self._modify_permission(user_id, operator_id, self.PERMISSION_MAP[self.ROLE_ADMIN], self.PERM_LEVEL_ROOT, 'add')

    async def delete_administrator(self, user_id: int, operator_id: int):
        """删除管理员"""
        await self._modify_permission(user_id, operator_id, self.PERMISSION_MAP[self.ROLE_ADMIN], self.PERM_LEVEL_ROOT, 'remove')

    async def add_to_blacklist(self, user_id: int, operator_id: int):
        """添加用户到黑名单"""
        await self._modify_permission(user_id, operator_id, self.PERMISSION_MAP[self.ROLE_BLACKLIST], self.PERM_LEVEL_ADMIN, 'add')

    async def remove_from_blacklist(self, user_id: int, operator_id: int):
        """从黑名单中移除用户"""
        if self._get_user_permission_level(user_id) >= self.PERM_LEVEL_ADMIN:
            raise PermissionError("无法将管理员或更高权限者从黑名单移除（他们本身也不应在黑名单中）。")
        await self._modify_permission(user_id, operator_id, self.PERMISSION_MAP[self.ROLE_BLACKLIST], self.PERM_LEVEL_ADMIN, 'remove')
    
    async def _sync_to_db(self, user_id: int, permission_type: str, operator_id: int, action: str):
        """
        将单条权限变更同步到数据库。
        
        Args:
            user_id (int): 目标用户ID
            permission_type (str): 权限类型 ('administrator' 或 'blacklist')
            operator_id (int): 操作者ID
            action (str): 'add' 或 'remove'
        """
        try:
            if action == 'add':
                sql = """
                    INSERT INTO permissions (user_id, permission_type, granted_by)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        permission_type = VALUES(permission_type), 
                        granted_by = VALUES(granted_by),
                        updated_at = CURRENT_TIMESTAMP
                """
                await self.db.execute_SQL(sql, (user_id, permission_type, operator_id))
            elif action == 'remove':
                sql = "DELETE FROM permissions WHERE user_id = %s"
                await self.db.execute_SQL(sql, (user_id,))
            
            self.logging.info(f"数据库同步成功: 用户 {user_id}, 权限 {permission_type}, 操作 {action}.")
        except Exception as e:
            self.logging.error(f"同步权限到数据库失败: {e}", exc_info=True)
            self.sync_from_db()
            raise IOError(f"同步权限到数据库失败: {e}\n已经尝试回滚")

    async def sync_from_db(self):
        """从数据库加载所有权限信息，并同步到本地内存中。"""
        self.logging.info("正在从数据库同步权限到本地...")
        try:
            sql = "SELECT user_id, permission_type FROM permissions"
            results = await self.db.execute_SQL(sql, ())
            
            self.administrator.clear()
            self.blacklist.clear()

            for user_id, permission_type in results:
                if permission_type == self.ROLE_ADMIN:
                    self.administrator.add(user_id)
                elif permission_type == self.ROLE_BLACKLIST:
                    self.blacklist.add(user_id)
                elif permission_type == self.ROLE_ROOT:
                    self.root.add(user_id)

            self.logging.info("从数据库同步权限到本地成功。")
            self.logging.info(f"加载权限\n - Root: {self.root},\n - Admin: {self.administrator},\n - Blacklist: {self.blacklist}")

        except Exception as e:
            self.logging.error(f"从数据库同步权限到本地失败: {e}", exc_info=True)
            raise IOError(f"从数据库同步权限到本地失败: {e}")

    def check_access(self, user_id: int) -> bool:
        """检查用户是否被拦截。不在黑名单中则返回True，表示允许访问"""
        return self._get_user_permission_level(user_id) > self.PERM_LEVEL_BLACKLIST

    def view_permissions(self) -> tuple[Set[int], Set[int]]:
        """查看现有的权限划分情况"""
        self.logging.info(f"Root: {self.root}, Administrator: {self.administrator}")
        return self.root, self.administrator

    def get_my_permission(self, user_id: int) -> str:
        """查看自己的权限角色"""
        role = self._get_user_role(user_id)
        return role

    def has_permission(self, user_id: int, required_level: int) -> bool:
        """
        判断用户是否有执行某个操作所需的权限
        Raises:
            PermissionError: 当用户权限不足时
        """
        user_level = self._get_user_permission_level(user_id)
        if user_level >= required_level:
            return True
        else:
            raise PermissionError(f"权限不足：需要等级 {required_level}，但用户 {user_id} 只有等级 {user_level}。")