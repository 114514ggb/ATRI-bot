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

-- 4. 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;

-- 5. 优化向量索引配置
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

-- 创建记忆表相关的枚举类型
DO $$
BEGIN
    CREATE TYPE memory_category AS ENUM (
        'preference',    -- 用户偏好
        'fact',          -- 事实性记忆
        'experience',    -- 经历记忆
        'emotion',       -- 情感记忆
        'group_topic',   -- 群聊话题或群体共识
        'knowledge',     -- 通用知识条目
        'domain',        -- 领域专业知识
        'guideline'      -- 行为准则知识
    );
EXCEPTION
    WHEN duplicate_object THEN 
        RAISE NOTICE 'Type memory_category already exists, skipping';
END $$;

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
   3. 依赖表结构 (Info, Permissions, Message, Memory, Context)
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
    time BIGINT, -- Unix 时间戳
    message_content TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);
-- 数据导入后可能需要重置序列：
-- SELECT setval('message_sole_id_seq', (SELECT COALESCE(MAX(sole_id), 0) FROM message));

-- 记忆表旧
-- CREATE TABLE IF NOT EXISTS atri_memory (
--     memory_id BIGSERIAL PRIMARY KEY,    -- 唯一id
--     group_id BIGINT DEFAULT 0,          -- 0或NULL私聊, 和user_id一起为NULL=知识库
--     user_id BIGINT,                     -- NULL=知识库
--     event_time BIGINT NOT NULL,         -- 记忆的时间
--     event TEXT,                         -- 记忆的文本
--     event_vector VECTOR(1024),          -- 向量
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 存入的时间
--     CONSTRAINT uq_user_event UNIQUE (user_id, event)
-- );

-- 记忆表新
CREATE TABLE IF NOT EXISTS atri_memory (
    memory_id   BIGSERIAL PRIMARY KEY,
    user_id     BIGINT,
    group_id    BIGINT,             -- NULL=知识库, 0=私聊, 其他=具体群
    event_time  BIGINT NOT NULL,    -- 记忆对应的事件时间,这个不一定和数据库时间一致，可能补充一个时间的记忆
    --   user_id IS NULL  AND group_id IS NULL → 知识库
    --   user_id NOT NULL AND group_id = 0     → 私聊记忆
    --   user_id NOT NULL AND group_id != 0    → 群聊中的用户记忆
    --   user_id IS NULL  AND group_id != 0    → 群聊公共记忆/话题
    --   或许不严格按照这样也行,知识库绑定一个user或group,什么的?
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 写入DB的时间
    event           TEXT,           -- 记忆的文本内容,应该长度大于2,这个就没必要在数据库层面限制了
    event_vector    VECTOR(1024),   -- 语义向量
    category    memory_category NOT NULL DEFAULT 'fact', -- 记忆类型
    -- 大概被分为:用户偏好,事实性记忆,经历记忆,情感记忆,群聊话题,通用知识条目,领域专业知识,行为准则
    -- 种类决定查询的随时间衰减的权重什么的
    importance  SMALLINT NOT NULL DEFAULT 5             -- 重要度 1~10
                    CHECK (importance  BETWEEN 1 AND 10),
    credibility SMALLINT NOT NULL DEFAULT 5             -- 可信度 1~10
                    CHECK (credibility BETWEEN 1 AND 10),
    access_count    INT NOT NULL DEFAULT 0,          -- 被检索命中的次数
    last_accessed   TIMESTAMP,                       -- 最后一次被检索的时间
    CONSTRAINT uq_user_event_hash UNIQUE (user_id, event),--同一用户不允许记忆的文本重复
    CONSTRAINT chk_quality_both_set CHECK (
        (importance IS NOT NULL AND credibility IS NOT NULL)
    ),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);


-- 上下文缓存表：存储每个用户的AI对话上下文
CREATE TABLE IF NOT EXISTS chat_context (
    context_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,                                     -- 私聊上下文
    group_id BIGINT,                                    -- 群聊上下文
    context_data JSONB NOT NULL DEFAULT '[]',           -- 消息数组 [{role, content, timestamp}, ...]
    total_tokens INT DEFAULT 0,                         -- 预估token数
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 最后更新时间
    CONSTRAINT chk_owner_exclusive CHECK (
        (user_id IS NOT NULL AND group_id IS NULL) OR   --只能有一个
        (user_id IS NULL AND group_id IS NOT NULL)
    ),
    CONSTRAINT uq_chat_context_user UNIQUE (user_id),
    CONSTRAINT uq_chat_context_group UNIQUE (group_id), -- 要唯一
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE CASCADE ON UPDATE CASCADE  
);

/* ==========================================================================
   4. 索引定义 (Indexes)
   ========================================================================== */

-- 消息表：查询某用户按时间倒序的消息
CREATE INDEX IF NOT EXISTS idx_message_user_time ON message(user_id, time DESC);

-- 用户信息表：JSONB GIN 索引，加速 JSON 查询 目前没必要
-- CREATE INDEX IF NOT EXISTS idx_user_info_info_gin ON user_info USING GIN (info);

-- 记忆表：普通查询索引
CREATE INDEX IF NOT EXISTS idx_atri_memory_user_time ON atri_memory (user_id, event_time);

-- 记忆表：HNSW 向量索引 (余弦距离)
CREATE INDEX IF NOT EXISTS idx_atri_memory_vector 
ON atri_memory 
USING hnsw (event_vector vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- 记忆表：按分类过滤
CREATE INDEX IF NOT EXISTS idx_atri_memory_category
    ON atri_memory (category);

-- 记忆表：知识库专用
CREATE INDEX IF NOT EXISTS idx_atri_memory_knowledge
    ON atri_memory (category, importance DESC)
    WHERE user_id IS NULL;

-- 记忆表：群聊记忆按群组过滤
CREATE INDEX IF NOT EXISTS idx_atri_memory_group
    ON atri_memory (group_id, event_time DESC)
    WHERE group_id IS NOT NULL AND group_id != 0;

-- 记忆表：PGroonga 全文检索索引
CREATE INDEX idx_atri_memory_event_pgroonga ON atri_memory USING pgroonga (event);

-- 快速查询指定用户的上下文
CREATE INDEX IF NOT EXISTS idx_chat_context_user_id 
    ON chat_context(user_id) 
    WHERE user_id IS NOT NULL;

-- 快速查询指定群组的上下文  
CREATE INDEX IF NOT EXISTS idx_chat_context_group_id 
    ON chat_context(group_id) 
    WHERE group_id IS NOT NULL;
    
/* ==========================================================================
   5. 触发器定义 (Triggers)
   ========================================================================== */

-- 通用触发器函数：自动更新 last_updated 时间戳
CREATE OR REPLACE FUNCTION update_timestamp_func()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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

-- chat_context 表自动更新
CREATE TRIGGER trg_chat_context_update_timestamp
    BEFORE UPDATE ON chat_context
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

/* ==========================================================================
   6. 注释 (Comments)
   ========================================================================== */

COMMENT ON TABLE user_group IS '群组表,存了bot接收过消息的群';
COMMENT ON TABLE users IS '用户表,存储了接收过消息的user';
COMMENT ON TABLE user_info IS '用户画像表';
COMMENT ON TABLE permissions IS '权限控制表';
COMMENT ON TABLE message IS '接收过的聊天记录消息表';
COMMENT ON TABLE chat_context IS '聊天的上下文缓存表';
COMMENT ON TABLE atri_memory IS '记忆表：存储用户记忆、群聊话题及知识库条目，支持向量检索与全文检索';

COMMENT ON COLUMN atri_memory.user_id IS
    'NULL=知识库条目；有值=用户相关记忆';
COMMENT ON COLUMN atri_memory.group_id IS
    'NULL=知识库；0=私聊；正整数=群聊ID';
COMMENT ON COLUMN atri_memory.event_time IS
    '记忆对应的事件发生时间，Unix时间戳（秒）';
COMMENT ON COLUMN atri_memory.importance IS
    '重要度1~10：1~3日常闲聊；4~6有价值信息；7~9重要个人信息；10极其重要';
COMMENT ON COLUMN atri_memory.credibility IS
    '可信度1~10：取代source字段，综合表达信息的可靠程度';
COMMENT ON COLUMN atri_memory.access_count IS
    '检索命中次数，高频记忆可在排序时获得额外加权';