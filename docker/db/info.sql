DROP DATABASE IF EXISTS atri;
DROP USER IF EXISTS atri;

CREATE USER atri WITH PASSWORD '180710';
CREATE DATABASE atri OWNER atri;

\c atri

GRANT ALL ON SCHEMA public TO atri;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE permission_type AS ENUM ('blacklist', 'administrator', 'root');

--群组表
CREATE TABLE user_group (
    group_id BIGINT NOT NULL PRIMARY KEY,
    group_name VARCHAR(45) NOT NULL
);

--用户表
CREATE TABLE users (
    user_id BIGINT NOT NULL PRIMARY KEY,
    nickname VARCHAR(45) NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--用户信息表 (JSON)
CREATE TABLE user_info (
    user_id BIGINT NOT NULL PRIMARY KEY,
    info JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

--权限表
CREATE TABLE permissions (
    user_id BIGINT NOT NULL PRIMARY KEY,
    permission_type permission_type NOT NULL,
    granted_by BIGINT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(user_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

--消息表
CREATE TABLE message (
    sole_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    group_id BIGINT,
    time BIGINT,
    message_content TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- 上下文缓存表
CREATE TABLE IF NOT EXISTS chat_context (
    context_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,                                     -- 私聊上下文
    group_id BIGINT,                                    -- 群聊上下文
    context_data JSONB NOT NULL DEFAULT '[]',           -- 消息数组 [{role, content, timestamp}, ...]
    total_tokens INT DEFAULT 0,                         -- 预估token数
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 最后更新时间
    CONSTRAINT chk_owner_exclusive CHECK (
        (user_id IS NOT NULL AND group_id IS NULL) OR  --只能有一个
        (user_id IS NULL AND group_id IS NOT NULL)
    ),
    CONSTRAINT uq_chat_context_user UNIQUE (user_id),
    CONSTRAINT uq_chat_context_group UNIQUE (group_id), -- 要唯一
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE CASCADE ON UPDATE CASCADE  
);

--记忆表
CREATE TABLE atri_memory (
    memory_id BIGSERIAL PRIMARY KEY,
    group_id BIGINT DEFAULT 0,  -- 默认值 0 表示私聊
    user_id BIGINT,             -- 允许 NULL 表示知识库记忆
    event_time BIGINT NOT NULL, -- 记忆的时间点
    event TEXT,                 -- 记忆文本
    event_vector VECTOR(1024),  -- 1024 维向量
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_event UNIQUE (user_id, event)
);

-- 消息表时间索引
CREATE INDEX idx_message_user_time ON message(user_id, time DESC);

-- 用户信息 JSONB GIN 索引
CREATE INDEX idx_user_info_info_gin ON user_info USING GIN (info);

-- 记忆表常规索引
CREATE INDEX idx_atri_memory_user_time ON atri_memory (user_id, event_time);

-- 快速查询用户的上下文
CREATE INDEX IF NOT EXISTS idx_chat_context_user_id ON chat_context(user_id) WHERE user_id IS NOT NULL;

-- 快速查询指定群组的上下文  
CREATE INDEX IF NOT EXISTS idx_chat_context_group_id ON chat_context(group_id) WHERE group_id IS NOT NULL;

-- 记忆表 HNSW 向量索引
CREATE INDEX idx_atri_memory_vector
ON atri_memory
USING hnsw (event_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 通用时间戳更新函数
CREATE OR REPLACE FUNCTION update_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 用户表触发器
CREATE TRIGGER trigger_update_users_last_updated
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated();

-- 用户信息表触发器
CREATE TRIGGER trigger_update_user_info_last_updated
    BEFORE UPDATE ON user_info
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated();

-- 权限表触发器
CREATE TRIGGER trigger_update_permissions_last_updated
    BEFORE UPDATE ON permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated();

-- 上下文表触发器
CREATE TRIGGER trg_chat_context_update_timestamp
    BEFORE UPDATE ON chat_context
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

ALTER DATABASE atri SET hnsw.ef_search = 100;

COMMENT ON TABLE user_group IS '群组表';
COMMENT ON TABLE users IS '用户表';
COMMENT ON TABLE message IS '消息表';
COMMENT ON TABLE permissions IS '权限表';
COMMENT ON TABLE atri_memory IS '记忆存储表，支持群聊、私聊和知识库记忆';

COMMENT ON COLUMN atri_memory.group_id IS '群组ID，0=私聊，NULL=知识库记忆';
COMMENT ON COLUMN atri_memory.user_id IS '用户ID，NULL=知识库记忆';
COMMENT ON COLUMN atri_memory.event_time IS '记忆时间戳';
COMMENT ON COLUMN atri_memory.event IS '事件描述文本';
COMMENT ON COLUMN atri_memory.event_vector IS '事件向量嵌入(1024维)';

ALTER TABLE user_group OWNER TO atri;
ALTER TABLE users OWNER TO atri;
ALTER TABLE user_info OWNER TO atri;
ALTER TABLE permissions OWNER TO atri;
ALTER TABLE message OWNER TO atri;
ALTER TABLE atri_memory OWNER TO atri;
ALTER TABLE chat_context OWNER TO atri;