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
      (SELECT array_length(regexp_matches(m.message_content, '亚托莉', 'g'), 1) AS cnt) AS t
GROUP BY m.group_id, g.group_name, m.user_id, u.nickname
ORDER BY "次数" DESC;



-- 查询数据库中所有表的大小，并按大小降序排列
SELECT schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;