-- mysqldump -u root -p atri > atri.sql

CREATE USER atri WITH PASSWORD '180710';

create database atri;
ALTER DATABASE atri OWNER TO atri;

-- 群组表
CREATE TABLE user_group (
    group_id BIGINT NOT NULL PRIMARY KEY,
    group_name VARCHAR(45) NOT NULL
);

-- 用户表
CREATE TABLE users (
    user_id BIGINT NOT NULL PRIMARY KEY,
    nickname VARCHAR(45) NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TYPE permission_type AS ENUM ('blacklist', 'administrator', 'root');

-- 权限表
CREATE TABLE permissions (
    user_id BIGINT NOT NULL PRIMARY KEY,
    permission_type permission_type NOT NULL,
    granted_by BIGINT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(user_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- 消息表 
--SELECT setval('message_sole_id_seq', (SELECT COALESCE(MAX(sole_id), 0) FROM message));
--导入后可能要重置到最大
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

--时间索引
CREATE INDEX idx_message_time_desc
ON message USING btree ("time" DESC);


-- 用户表的last_updated字段更新触发器
CREATE OR REPLACE FUNCTION update_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_users_last_updated
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated();

-- 为权限表的updated_at字段创建更新触发器
CREATE TRIGGER trigger_update_permissions_updated_at
    BEFORE UPDATE ON permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated();

-- 创建记忆表
CREATE TABLE atri_memory (
    memory_id BIGSERIAL PRIMARY KEY,
    group_id BIGINT DEFAULT 0,  -- 默认值 0 表示私聊,为0时user_id不能为空
    user_id BIGINT,             -- 允许和group_id一起为 NULL 表示知识库记忆
    event_time BIGINT NOT NULL, -- 记忆的时间点
    event TEXT,                 -- 记忆文本
    event_vector VECTOR(1024),  -- 1024 维向量
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP --创建时间
);

-- 添加注释说明字段用途
COMMENT ON COLUMN atri_memory.group_id IS '群组ID，0=私聊，NULL=知识库记忆';
COMMENT ON COLUMN atri_memory.user_id IS '用户ID，NULL=知识库记忆';
COMMENT ON COLUMN atri_memory.event_time IS '记忆时间戳';
COMMENT ON COLUMN atri_memory.event IS '事件描述文本';
COMMENT ON COLUMN atri_memory.event_vector IS '事件向量嵌入(1024维)';

-- 添加注释
COMMENT ON TABLE user_group IS '群组表';
COMMENT ON TABLE users IS '用户表';
COMMENT ON TABLE message IS '消息表';
COMMENT ON TABLE permissions IS '权限表';
COMMENT ON TABLE atri_memory IS '记忆存储表，支持群聊、私聊和知识库记忆';

-- sudo apt install postgresql-16-pgvector
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