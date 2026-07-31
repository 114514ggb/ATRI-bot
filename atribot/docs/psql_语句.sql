SELECT memory_id, event, user_id
FROM atri_memory
ORDER BY created_at DESC
LIMIT 50;


SELECT
    m.group_id  AS "群号",
    m.user_id   AS "qq号",
    u.nickname  AS "网名",
    COUNT(*)    AS "发言次数",
    DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS "名次"
FROM message m
JOIN users u ON u.user_id = m.user_id
WHERE m.group_id = 936819059
GROUP BY m.group_id, m.user_id, u.nickname
ORDER BY "发言次数" DESC;


SELECT
    m.group_id  AS "群号",
    m.user_id   AS "qq号",
    u.nickname  AS "网名",
    COUNT(*)    AS "发言次数",
    DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS "名次"
FROM message m
JOIN users u ON u.user_id = m.user_id
WHERE m.group_id = 936819059
  AND m.time >= EXTRACT(EPOCH FROM (CURRENT_DATE - INTERVAL '30 days'))::bigint
GROUP BY m.group_id, m.user_id, u.nickname
ORDER BY "发言次数" DESC;


SELECT
    m.group_id  AS "群号",
    m.user_id   AS "qq号",
    u.nickname  AS "网名",
    COUNT(*)    AS "发言次数",
    DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS "名次"
FROM message m
JOIN users u ON u.user_id = m.user_id
WHERE m.time >= EXTRACT(EPOCH FROM (CURRENT_DATE - INTERVAL '30 days'))::bigint
GROUP BY m.group_id, m.user_id, u.nickname
ORDER BY "发言次数" DESC;




SELECT SUM(coalesce(cnt, 0)) AS 出现总次数
FROM   message m
CROSS JOIN LATERAL
       (SELECT array_length(regexp_matches(m.message_content, '(?i)ATRI', 'g'), 1) AS cnt) AS t
WHERE  m.group_id = 936819059
  AND  m.time >= extract(epoch from date_trunc('day', now()))
  AND  m.time <  extract(epoch from date_trunc('day', now()) + interval '1 day');


SELECT
    m.group_id                     AS "群号",
    g.group_name                   AS "群名",
    m.user_id                      AS "用户ID",
    u.nickname                     AS "昵称",
    SUM(t.cnt)                     AS "次数",
    DENSE_RANK() OVER (ORDER BY SUM(t.cnt) DESC) AS "名次"
FROM message m
JOIN users      u ON u.user_id = m.user_id
JOIN user_group g ON g.group_id = m.group_id
CROSS JOIN LATERAL
      (SELECT array_length(regexp_matches(m.message_content, '(?i)ATRI', 'g'), 1) AS cnt) AS t
WHERE m.group_id = 936819059
  AND m.time >= EXTRACT(EPOCH FROM CURRENT_DATE - INTERVAL '30 days')
GROUP BY m.group_id, g.group_name, m.user_id, u.nickname
ORDER BY "次数" DESC;

SELECT
    m.group_id                     AS "群号",
    g.group_name                   AS "群名",
    m.user_id                      AS "用户ID",
    u.nickname                     AS "昵称",
    SUM(t.cnt)                     AS "次数",
    DENSE_RANK() OVER (ORDER BY SUM(t.cnt) DESC) AS "名次"
FROM message m
JOIN users      u ON u.user_id = m.user_id
JOIN user_group g ON g.group_id = m.group_id
CROSS JOIN LATERAL
      (SELECT array_length(regexp_matches(m.message_content, '\[CQ:at,qq=168238719\]', 'g'), 1) AS cnt) AS t
WHERE m.time >= EXTRACT(EPOCH FROM (CURRENT_DATE - INTERVAL '30 days'))
GROUP BY m.group_id, g.group_name, m.user_id, u.nickname
ORDER BY "次数" DESC;

SELECT
    m.user_id                      AS "用户ID",
    u.nickname                     AS "昵称",
    SUM(t.cnt)                     AS "次数",
    DENSE_RANK() OVER (ORDER BY SUM(t.cnt) DESC) AS "名次"
FROM message m
JOIN users      u ON u.user_id = m.user_id
CROSS JOIN LATERAL
      (SELECT array_length(regexp_matches(m.message_content, '\[CQ:at,qq=168238719\]', 'g'), 1) AS cnt) AS t
WHERE m.time >= EXTRACT(EPOCH FROM (CURRENT_DATE - INTERVAL '30 days'))::bigint
GROUP BY m.user_id, u.nickname
ORDER BY "次数" DESC;


SELECT
    t.group_id AS "群号",
    t.user_id AS "qq号",
    u.nickname AS "网名",
    COUNT(*) AS "调用次数",
    SUM(t.prompt_tokens) AS "输入token",
    SUM(t.completion_tokens) AS "输出token",
    SUM(t.total_tokens) AS "总消耗token",
    DENSE_RANK() OVER (ORDER BY SUM(t.total_tokens) DESC) AS "名次"
FROM token_statistics t
LEFT JOIN users u ON u.user_id = t.user_id
GROUP BY
    t.group_id,
    t.user_id,
    u.nickname
ORDER BY "总消耗token" DESC;

SELECT
    t.user_id AS "qq号",
    u.nickname AS "网名",
    COUNT(*) AS "调用次数",
    SUM(t.prompt_tokens) AS "输入token",
    SUM(t.completion_tokens) AS "输出token",
    SUM(t.total_tokens) AS "总消耗token",
    DENSE_RANK() OVER (ORDER BY SUM(t.total_tokens) DESC) AS "名次"
FROM token_statistics t
LEFT JOIN users u ON u.user_id = t.user_id
GROUP BY
    t.user_id,
    u.nickname
ORDER BY "总消耗token" DESC;


SELECT schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 列出数据库中所有表的大小
SELECT 
    schemaname as "模式",
    tablename as "表名",
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as "总大小",
    pg_size_pretty(pg_relation_size(schemaname || '.' || tablename)) as "表数据大小",
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename) - pg_relation_size(schemaname || '.' || tablename)) as "索引大小"
FROM pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;

UPDATE chat_context
SET context_data = '[]',
    total_tokens = 0
WHERE last_updated >= CURRENT_TIMESTAMP - INTERVAL '5 days';

SELECT 
    u.nickname,
    COUNT(am.memory_id) as memory_count
FROM atri_memory am
JOIN users u ON am.user_id = u.user_id
WHERE am.created_at BETWEEN '2024-01-01' AND '2026-1-1'
GROUP BY u.user_id, u.nickname
ORDER BY memory_count DESC
LIMIT 50;

-- 查看当前数据库中的所有触发器
SELECT * FROM pg_trigger WHERE NOT tgisinternal;

--删除非知识库记忆下面清除索引
DELETE FROM atri_memory
WHERE group_id IS NOT NULL 
   OR user_id IS NOT NULL;

VACUUM FULL atri_memory;
-- 不锁表
VACUUM ANALYZE atri_memory;

