# 数据库表结构改动记录

本文件集中记录对数据库表结构的所有改动。每次修改表结构时，需同时：

1. 在 `atribot/core/db/schema_migration.py` 的 `MIGRATIONS` 注册表中追加一条迁移记录（幂等，可重复执行）。
2. 在本文件追加一条改动说明。
3. 若涉及新库初始化，同步更新 `docker/db/info.sql` 与 `docker/db/init/01-init.sh` 中的建表语句。

> 迁移在数据库连接池创建后（`AsyncPostgreSQL.initialize()`）自动执行，失败只记 warning，不阻断启动。

---

## 001 - chat_context 表新增 play_role 列

- **日期**：2026-09-12
- **目的**：持久化 `/chat role <人设>` 切换的人设名称，使 Bot 重启后仍能按名字载入人设（无则使用默认人设）。
- **改动**：`chat_context` 表新增 `play_role VARCHAR(255)` 列，存储人设名称。
- **SQL**：

```sql
ALTER TABLE chat_context
ADD COLUMN IF NOT EXISTS play_role VARCHAR(255);
```

- **说明**：该列可为 `NULL`（旧数据无值），读取时若为空或不在人设列表内则回退默认人设。切换人设时通过 `save_user_role` / `save_group_role` 立即持久化。