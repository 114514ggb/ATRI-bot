"""数据库表结构自动迁移模块

集中管理所有历史表结构改动。每次对数据库表结构做修改时，都应在此模块追加一条迁移记录，
并在 `atribot/docs/db_migrations.md` 中登记说明。

迁移在数据库连接池创建后（`AsyncPostgreSQL.initialize()`）自动执行：
- 每条迁移先检查目标列/对象是否已存在（幂等），存在则跳过，不存在才执行 ALTER。
- 迁移失败只记录 warning,不阻断 Bot 启动
"""
from dataclasses import dataclass
from logging import Logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atribot.core.db.async_postgresql import AsyncPostgreSQL


@dataclass(frozen=True)
class Migration:
    """一条数据库迁移记录"""

    version: str
    """迁移版本号，如 '001'"""
    description: str
    """迁移说明"""
    check_sql: str
    """用于判断目标对象是否已存在的 SQL,返回一行一列（存在则非空）"""
    apply_sql: str
    """实际执行的迁移 SQL(幂等,可重复执行)"""


#迁移注册表
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="001",
        description="chat_context 表新增 play_role 列，用于持久化人设名称",
        check_sql=(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'chat_context' AND column_name = 'play_role'"
        ),
        apply_sql=(
            "ALTER TABLE chat_context "
            "ADD COLUMN IF NOT EXISTS play_role VARCHAR(255)"
        ),
    ),
    Migration(
        version="002",
        description="atri_memory 表新增 created_at DESC 索引，加速无向量浏览查询",
        check_sql=(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename = 'atri_memory' AND indexname = 'idx_atri_memory_created'"
        ),
        apply_sql=(
            "CREATE INDEX IF NOT EXISTS idx_atri_memory_created "
            "ON atri_memory (created_at DESC)"
        ),
    ),
)


async def run_migrations(db: AsyncPostgreSQL, log: Logger | None = None) -> None:
    """执行所有未应用的数据库迁移

    Args:
        db: 数据库连接池实例
        log: 日志器，缺省时使用 db 自带日志
    """
    logger = log or db.log

    for migration in MIGRATIONS:
        try:
            async with db as conn:
                exists = await conn.execute_with_pool(
                    query=migration.check_sql,
                    fetch_type="one",
                )
            if exists:
                logger.debug(
                    "迁移 %s 已应用，跳过: %s",
                    migration.version,
                    migration.description,
                )
                continue

            async with db as conn:
                await conn.execute_with_pool(query=migration.apply_sql)

            logger.info(
                "数据库迁移 %s 已执行: %s",
                migration.version,
                migration.description,
            )
        except Exception as e:
            logger.warning(
                "数据库迁移 %s 执行失败（不阻断启动）: %s - %s",
                migration.version,
                migration.description,
                e,
            )