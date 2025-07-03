create database atri;

-- 群组表
CREATE TABLE user_group (
    group_id BIGINT NOT NULL PRIMARY KEY,
    group_name VARCHAR(45) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用户表
CREATE TABLE users (
    user_id BIGINT NOT NULL PRIMARY KEY,
    nickname VARCHAR(45) NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 消息表 
CREATE TABLE message (
    sole_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, 
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    group_id BIGINT,
    time BIGINT,
    message_content TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_group(group_id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;