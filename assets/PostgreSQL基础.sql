-- mysqldump -u root -p atri > atri.sql

-- sudo apt install postgresql-18-pgvector
-- 提供向量支持的插件
-- create extension vector;
-- CREATE EXTENSION IF NOT EXISTS vector;
-- 查看插件
-- SELECT * FROM pg_available_extensions;#

--pgvector支持的距离函数如下:
-- <-> - L2 distance(欧几里得距离)
-- <#> - (negative) inner product
-- <=> - cosine distance(余弦)
-- <+> - L1 distance (added in 0.7.0)
-- <~> - Hamming distance (binary vectors, added in 0.7.0)
-- <%> - Jaccard distance (binary vectors, added in 0.7.0)

-- 1. 创建用户
-- CREATE USER atri WITH PASSWORD '180710';

-- 2. 创建数据库并指定所有者
-- CREATE DATABASE atri OWNER atri;

-- 3. 连接到 atri 数据库后执行以下操作：
-- \c atri

-- 4. 启用 pgvector 扩展 (必须先安装: sudo apt install postgresql-xx-pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

-- 5. 优化向量索引配置 (根据需要开启)
ALTER SYSTEM SET hnsw.ef_search = 100;
-- SELECT pg_reload_conf();

/* ==========================================================================
   1. 清理与枚举定义
   ========================================================================== */

-- 创建权限枚举类型
DO $$ BEGIN
    CREATE TYPE permission_type AS ENUM ('blacklist', 'administrator', 'root');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 通用触发器函数：自动更新 last_updated 时间戳
CREATE OR REPLACE FUNCTION update_timestamp_func()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


/* ==========================================================================
   2. 基础表结构 (Users, Groups)
   ========================================================================== */

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT NOT NULL PRIMARY KEY,
    nickname VARCHAR(45) NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 群组表
CREATE TABLE IF NOT EXISTS user_group (
    group_id BIGINT NOT NULL PRIMARY KEY,
    group_name VARCHAR(45) NOT NULL
);


/* ==========================================================================
   3. 依赖表结构 (Info, Permissions, Message, Memory)
   ========================================================================== */

-- 用户信息 JSON 表
CREATE TABLE IF NOT EXISTS user_info (
    user_id BIGINT NOT NULL PRIMARY KEY,
    info JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- 权限表
CREATE TABLE IF NOT EXISTS permissions (
    user_id BIGINT NOT NULL PRIMARY KEY,
    permission_type permission_type NOT NULL,
    granted_by BIGINT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(user_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- 消息表
CREATE TABLE IF NOT EXISTS message (
    sole_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    group_id BIGINT,
    time BIGINT, -- 推荐存储 Unix 时间戳
    message_content TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);
-- 数据导入后可能需要重置序列：
-- SELECT setval('message_sole_id_seq', (SELECT COALESCE(MAX(sole_id), 0) FROM message));

-- 记忆表 (支持向量检索)
CREATE TABLE IF NOT EXISTS atri_memory (
    memory_id BIGSERIAL PRIMARY KEY,
    group_id BIGINT DEFAULT 0,  -- 0=私聊, NULL=知识库, 其他=群聊
    user_id BIGINT,             -- NULL=知识库
    event_time BIGINT NOT NULL,
    event TEXT,
    event_vector VECTOR(1024),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_event UNIQUE (user_id, event)
);


/* ==========================================================================
   4. 索引定义 (Indexes)
   ========================================================================== */

-- 消息表：查询某用户按时间倒序的消息
CREATE INDEX IF NOT EXISTS idx_message_user_time ON message(user_id, time DESC);

-- 用户信息表：JSONB GIN 索引，加速 JSON 查询
CREATE INDEX IF NOT EXISTS idx_user_info_info_gin ON user_info USING GIN (info);

-- 记忆表：普通查询索引
CREATE INDEX IF NOT EXISTS idx_atri_memory_user_time ON atri_memory (user_id, event_time);

-- 记忆表：HNSW 向量索引 (余弦距离)
CREATE INDEX IF NOT EXISTS idx_atri_memory_vector 
ON atri_memory 
USING hnsw (event_vector vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);


/* ==========================================================================
   5. 触发器定义 (Triggers)
   ========================================================================== */

-- Users 表自动更新
CREATE TRIGGER trg_users_update_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

-- User_info 表自动更新
CREATE TRIGGER trg_user_info_update_timestamp
    BEFORE UPDATE ON user_info
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

-- Permissions 表自动更新
CREATE TRIGGER trg_permissions_update_timestamp
    BEFORE UPDATE ON permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();


/* ==========================================================================
   6. 注释 (Comments)
   ========================================================================== */

COMMENT ON TABLE user_group IS '群组基础信息表';
COMMENT ON TABLE users IS '用户基础信息表';
COMMENT ON TABLE user_info IS '用户扩展信息(JSON)表';
COMMENT ON TABLE permissions IS '用户权限控制表';
COMMENT ON TABLE message IS '聊天记录消息表';
COMMENT ON TABLE atri_memory IS 'RAG记忆存储表，包含向量数据';

COMMENT ON COLUMN atri_memory.group_id IS '群组ID，0=私聊，NULL=知识库记忆';
COMMENT ON COLUMN atri_memory.user_id IS '用户ID，NULL=知识库记忆';
COMMENT ON COLUMN atri_memory.event_time IS '记忆发生的Unix时间戳';
COMMENT ON COLUMN atri_memory.event IS '原始文本内容';
COMMENT ON COLUMN atri_memory.event_vector IS '文本嵌入向量(1024维)';