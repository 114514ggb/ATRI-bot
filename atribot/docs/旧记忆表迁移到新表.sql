-- ============================================================
-- Step 1: 旧表改名(注意做之前加入了插件)
-- ============================================================
ALTER TABLE atri_memory RENAME TO atri_memory_old;


-- ============================================================
-- Step 2: 建新表
-- ============================================================
CREATE TYPE memory_category AS ENUM (
    'preference',   -- 用户偏好
    'fact',         -- 事实性记忆
    'experience',   -- 经历记忆
    'emotion',      -- 情感记忆
    'topic',        -- 群聊话题
    'knowledge',    -- 通用知识条目
    'domain',       -- 领域专业知识
    'guideline'     -- 行为准则
);

CREATE TABLE IF NOT EXISTS atri_memory (
    memory_id       BIGSERIAL PRIMARY KEY,
    user_id         BIGINT,
    group_id        BIGINT,
    event_time      BIGINT NOT NULL,
    created_at      BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)::bigint,
    event           TEXT,
    event_vector    VECTOR(1024),
    category        memory_category NOT NULL DEFAULT 'fact',
    importance      SMALLINT NOT NULL DEFAULT 5 CHECK (importance  BETWEEN 1 AND 10),
    credibility     SMALLINT NOT NULL DEFAULT 5 CHECK (credibility BETWEEN 1 AND 10),
    access_count    INT NOT NULL DEFAULT 0,
    last_accessed   BIGINT,
    CONSTRAINT uq_user_event_hash UNIQUE (user_id, event),
    CONSTRAINT chk_quality_both_set CHECK (
        importance IS NOT NULL AND credibility IS NOT NULL
    ),
    FOREIGN KEY (user_id)  REFERENCES users(user_id)
        ON DELETE CASCADE  ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);


-- ============================================================
-- Step 3: 从旧表迁移数据
-- ============================================================
INSERT INTO atri_memory (
    user_id,
    group_id,
    event_time,
    created_at,
    event,
    event_vector,
    category,
    importance,
    credibility,
    access_count,
    last_accessed
)
SELECT
    user_id,
    CASE WHEN group_id = 0 THEN NULL ELSE group_id END,
    event_time,
    EXTRACT(EPOCH FROM created_at)::bigint,     -- TIMESTAMP → Unix秒
    event,
    event_vector,
    'fact'::memory_category,                    -- 旧数据统一默认
    5,
    5,
    0,
    NULL
FROM atri_memory_old
WHERE event IS NOT NULL
  AND length(trim(event)) > 2
ON CONFLICT (user_id, event) DO NOTHING;       -- 重复直接跳过


-- ============================================================
-- Step 4: 验证数量
-- ============================================================
SELECT
    (SELECT COUNT(*) FROM atri_memory_old) AS old_count,
    (SELECT COUNT(*) FROM atri_memory)     AS new_count,
    (SELECT COUNT(*) FROM atri_memory_old) -
    (SELECT COUNT(*) FROM atri_memory)     AS skipped;


-- ============================================================
-- Step 5: 确认无误后删除旧表（不急的话多观察几天再删）
-- ============================================================
-- DROP TABLE atri_memory_old;