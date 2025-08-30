mysqldump -u root -p --single-transaction --routines --triggers --events --default-character-set=utf8mb4 atri > atri.sql

SELECT 
    m.group_id AS `群号`,
    m.user_id AS `qq号`,
    u.nickname AS `网名`,
    COUNT(m.message_id) AS `发言次数`,
    DENSE_RANK() OVER (ORDER BY COUNT(m.message_id) DESC) AS `名次`
FROM 
    atri.message m
LEFT JOIN 
    atri.users u ON m.user_id = u.user_id
WHERE 
    m.group_id = 936819059 
GROUP BY 
    m.group_id, m.user_id
ORDER BY 
    `发言次数` DESC;


SELECT 
    m.group_id AS `群号`,
    m.user_id AS `qq号`,
    u.nickname AS `网名`,
    COUNT(m.message_id) AS `发言次数`,
    DENSE_RANK() OVER (ORDER BY COUNT(m.message_id) DESC) AS `名次`
FROM 
    atri.message m
LEFT JOIN 
    atri.users u ON m.user_id = u.user_id
WHERE 
    m.group_id = 936819059
    AND m.time >= UNIX_TIMESTAMP(CURRENT_DATE() - INTERVAL 30 DAY)
GROUP BY 
    m.group_id, m.user_id
ORDER BY 
    `发言次数` DESC;






# 查询每个群发言次数最多的用户
SELECT group_id, user_id, COUNT(*) AS message_count
FROM message
GROUP BY group_id, user_id
HAVING (group_id, COUNT(*)) IN (
    SELECT group_id, MAX(msg_count)
    FROM (
        SELECT group_id, user_id, COUNT(*) AS msg_count
        FROM message
        GROUP BY group_id, user_id
    ) AS sub
    GROUP BY group_id
);



SET @target_group_id = 1062704755;
SET @start_date = '2023-01-01 00:00:00';

SELECT 
    COUNT(*) AS '包含@的行数' 
FROM 
    atri.message AS m
JOIN
    atri.user_group AS g ON m.group_id = g.group_id
WHERE 
    m.group_id = @target_group_id 
    AND m.message_content LIKE '%[CQ:at,qq=168238719]%' 
    AND m.time > UNIX_TIMESTAMP(@start_date)
ORDER BY 
    '包含@的行数' DESC;


SELECT 
    m.group_id AS '群号',
    g.group_name AS '群名',
    m.user_id AS '用户ID',
    u.nickname AS '昵称',
    COUNT(*) AS '包含@的行数',
    DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS `名次`
FROM 
    atri.message m
JOIN 
    atri.users u ON m.user_id = u.user_id
JOIN 
    atri.user_group g ON m.group_id = g.group_id
WHERE 
    m.group_id = 936819059
    AND m.message_content LIKE '%[CQ:at,qq=3761714582]%'
    AND m.time > UNIX_TIMESTAMP(@start_date)
GROUP BY
    m.group_id, g.group_name, m.user_id, u.nickname
ORDER BY
    `包含@的行数` DESC;



SET @target_group_id = 936819059;
SET @keyword = '生日快乐';
SET @start_date = '2025-08-28 00:00:00';

SELECT 
    SUM(LENGTH(message_content) - LENGTH(REPLACE(message_content, @keyword, ''))) / LENGTH(@keyword) AS '次数' 
FROM 
    atri.message 
WHERE 
    group_id = @target_group_id 
    AND message_content LIKE CONCAT('%', @keyword, '%') 
    AND time > UNIX_TIMESTAMP(@start_date)
ORDER BY 
    '总次数' DESC;


SET @keyword = '生日快乐';
SET @start_date = '2025-08-28 00:00:00';

SELECT
    g.group_id AS "群号",
    g.group_name AS "群名",
    u.user_id AS "用户ID",
    u.nickname AS "昵称",
    SUM(
        (LENGTH(m.message_content) - LENGTH(REPLACE(m.message_content, @keyword, ''))) / LENGTH(@keyword)
    ) AS "出现总次数",
    DENSE_RANK() OVER (
        ORDER BY SUM(
            (LENGTH(m.message_content) - LENGTH(REPLACE(m.message_content, @keyword, ''))) / LENGTH(@keyword)
        ) DESC
    ) AS `名次`
FROM
    atri.message m
JOIN
    atri.users u ON m.user_id = u.user_id
JOIN
    atri.user_group g ON m.group_id = g.group_id
WHERE
    m.message_content LIKE CONCAT('%', @keyword, '%')
    AND m.time > UNIX_TIMESTAMP(@start_date)
GROUP BY
    g.group_id, g.group_name, u.user_id, u.nickname
ORDER BY
    `出现总次数` DESC;
