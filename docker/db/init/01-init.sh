#!/bin/sh
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
DO
















\$\$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = '${ATRI_DB_NAME}') THEN
        EXECUTE format('DROP DATABASE %I', '${ATRI_DB_NAME}');
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${ATRI_DB_APP_USER}') THEN
        EXECUTE format('DROP ROLE %I', '${ATRI_DB_APP_USER}');
    END IF;
END
\$\$;

CREATE USER ${ATRI_DB_APP_USER} WITH PASSWORD '${ATRI_DB_APP_PASSWORD}';
CREATE DATABASE ${ATRI_DB_NAME} OWNER ${ATRI_DB_APP_USER};
EOSQL

export PGPASSWORD="$POSTGRES_PASSWORD"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$ATRI_DB_NAME" <<-EOSQL
GRANT ALL ON SCHEMA public TO ${ATRI_DB_APP_USER};

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;

CREATE TYPE permission_type AS ENUM ('blacklist', 'administrator', 'root');

CREATE TYPE memory_category AS ENUM (
    'preference',
    'fact',
    'experience',
    'emotion',
    'group_topic',
    'knowledge',
    'domain',
    'guideline'
);

CREATE TABLE user_group (
    group_id BIGINT NOT NULL PRIMARY KEY,
    group_name VARCHAR(45) NOT NULL
);

CREATE TABLE users (
    user_id BIGINT NOT NULL PRIMARY KEY,
    nickname VARCHAR(45) NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_info (
    user_id BIGINT NOT NULL PRIMARY KEY,
    info JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

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

CREATE TABLE IF NOT EXISTS chat_context (
    context_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    group_id BIGINT,
    context_data JSONB NOT NULL DEFAULT '[]',
    total_tokens INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_owner_exclusive CHECK (
        (user_id IS NOT NULL AND group_id IS NULL) OR
        (user_id IS NULL AND group_id IS NOT NULL)
    ),
    CONSTRAINT uq_chat_context_user UNIQUE (user_id),
    CONSTRAINT uq_chat_context_group UNIQUE (group_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE atri_memory (
    memory_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    group_id BIGINT,
    event_time BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event TEXT,
    event_vector VECTOR(1024),
    category memory_category NOT NULL DEFAULT 'fact',
    importance SMALLINT NOT NULL DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    credibility SMALLINT NOT NULL DEFAULT 5 CHECK (credibility BETWEEN 1 AND 10),
    access_count INT NOT NULL DEFAULT 0,
    last_accessed TIMESTAMP,
    CONSTRAINT uq_user_event_hash UNIQUE (user_id, event),
    CONSTRAINT chk_quality_both_set CHECK (
        (importance IS NOT NULL AND credibility IS NOT NULL)
    ),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX idx_message_user_time ON message(user_id, time DESC);
CREATE INDEX idx_atri_memory_user_time ON atri_memory (user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_chat_context_user_id ON chat_context(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_context_group_id ON chat_context(group_id) WHERE group_id IS NOT NULL;
CREATE INDEX idx_atri_memory_vector
ON atri_memory
USING hnsw (event_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_atri_memory_category ON atri_memory (category);
CREATE INDEX idx_atri_memory_knowledge
    ON atri_memory (category, importance DESC)
    WHERE user_id IS NULL;
CREATE INDEX idx_atri_memory_group
    ON atri_memory (group_id, event_time DESC)
    WHERE group_id IS NOT NULL AND group_id != 0;
CREATE INDEX idx_atri_memory_event_pgroonga ON atri_memory USING pgroonga (event);

CREATE OR REPLACE FUNCTION update_timestamp_func()
RETURNS TRIGGER AS \$\$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
\$\$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_update_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

CREATE TRIGGER trg_user_info_update_timestamp
    BEFORE UPDATE ON user_info
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

CREATE TRIGGER trg_permissions_update_timestamp
    BEFORE UPDATE ON permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

CREATE TRIGGER trg_chat_context_update_timestamp
    BEFORE UPDATE ON chat_context
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_func();

ALTER DATABASE ${ATRI_DB_NAME} SET hnsw.ef_search = 100;

COMMENT ON TABLE user_group IS '群组表,存了bot接收过消息的群';
COMMENT ON TABLE users IS '用户表,存储了接收过消息的user';
COMMENT ON TABLE user_info IS '用户画像表';
COMMENT ON TABLE permissions IS '权限控制表';
COMMENT ON TABLE message IS '接收过的聊天记录消息表';
COMMENT ON TABLE chat_context IS '聊天的上下文缓存表';
COMMENT ON TABLE atri_memory IS '记忆表：存储用户记忆、群聊话题及知识库条目，支持向量检索与全文检索';

COMMENT ON COLUMN atri_memory.user_id IS 'NULL=知识库条目；有值=用户相关记忆';
COMMENT ON COLUMN atri_memory.group_id IS 'NULL=知识库；0=私聊；正整数=群聊ID';
COMMENT ON COLUMN atri_memory.event_time IS '记忆对应的事件发生时间，Unix时间戳（秒）';
COMMENT ON COLUMN atri_memory.importance IS '重要度1~10：1~3日常闲聊；4~6有价值信息；7~9重要个人信息；10极其重要';
COMMENT ON COLUMN atri_memory.credibility IS '可信度1~10：取代source字段，综合表达信息的可靠程度';
COMMENT ON COLUMN atri_memory.access_count IS '检索命中次数，高频记忆可在排序时获得额外加权';

ALTER TABLE user_group OWNER TO ${ATRI_DB_APP_USER};
ALTER TABLE users OWNER TO ${ATRI_DB_APP_USER};
ALTER TABLE user_info OWNER TO ${ATRI_DB_APP_USER};
ALTER TABLE permissions OWNER TO ${ATRI_DB_APP_USER};
ALTER TABLE message OWNER TO ${ATRI_DB_APP_USER};
ALTER TABLE atri_memory OWNER TO ${ATRI_DB_APP_USER};
ALTER TABLE chat_context OWNER TO ${ATRI_DB_APP_USER};
EOSQL