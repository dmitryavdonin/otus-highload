-- Удаляем view
DROP VIEW IF EXISTS all_posts;

-- Удаляем все таблицы
DROP TABLE IF EXISTS dialog_messages;
DROP TABLE IF EXISTS posts_hot_users;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS friends;
DROP TABLE IF EXISTS auth_tokens;
DROP TABLE IF EXISTS users;

-- Создаем таблицы заново
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    first_name VARCHAR NOT NULL,
    second_name VARCHAR NOT NULL,
    birthdate DATE NOT NULL,
    biography VARCHAR,
    city VARCHAR,
    password VARCHAR NOT NULL,
    is_hot_user BOOLEAN DEFAULT FALSE,
    post_count INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token VARCHAR(64) PRIMARY KEY,
    user_id UUID NOT NULL,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS friends (
    user_id UUID,
    friend_id UUID,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    PRIMARY KEY (user_id, friend_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id UUID,
    text VARCHAR NOT NULL,
    author_user_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    PRIMARY KEY (id, author_user_id)
);

CREATE TABLE IF NOT EXISTS posts_hot_users (
    id UUID,
    text VARCHAR NOT NULL,
    author_user_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    time_bucket INT NOT NULL,
    PRIMARY KEY (id, author_user_id)
);

CREATE TABLE IF NOT EXISTS dialog_messages (
    id UUID,
    from_user_id UUID NOT NULL,
    to_user_id UUID NOT NULL,
    text VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    PRIMARY KEY (id, from_user_id)
);

-- Function to calculate time_bucket
CREATE OR REPLACE FUNCTION calculate_time_bucket(created_at TIMESTAMP) RETURNS INT AS $$
BEGIN
    RETURN EXTRACT(YEAR FROM created_at) * 100 + EXTRACT(MONTH FROM created_at);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create view for unified access to posts
CREATE OR REPLACE VIEW all_posts AS
SELECT id, text, author_user_id, created_at FROM posts
UNION ALL
SELECT id, text, author_user_id, created_at FROM posts_hot_users; 