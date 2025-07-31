-- Сначала создаем базу данных social_network, если она не существует
SELECT 'CREATE DATABASE social_network'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'social_network');

-- Переключаемся на базу данных social_network
\c social_network

-- Определяем, существуют ли таблицы
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    -- Проверяем существование таблицы users
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'users'
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Делаем users таблицей-справочником
        PERFORM create_reference_table('users');
        RAISE NOTICE 'users стала таблицей-справочником';
    ELSE
        RAISE NOTICE 'Таблица users не существует';
    END IF;

    -- Проверяем существование таблицы auth_tokens
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'auth_tokens'
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Делаем auth_tokens таблицей-справочником
        PERFORM create_reference_table('auth_tokens');
        RAISE NOTICE 'auth_tokens стала таблицей-справочником';
    ELSE
        RAISE NOTICE 'Таблица auth_tokens не существует';
    END IF;

    -- Проверяем существование таблицы friends
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'friends'
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Распределяем friends по user_id
        PERFORM create_distributed_table('friends', 'user_id');
        RAISE NOTICE 'friends распределена по user_id';
    ELSE
        RAISE NOTICE 'Таблица friends не существует';
    END IF;

    -- Проверяем существование таблицы posts
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'posts'
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Распределяем posts по author_user_id
        PERFORM create_distributed_table('posts', 'author_user_id');
        RAISE NOTICE 'posts распределена по author_user_id';
    ELSE
        RAISE NOTICE 'Таблица posts не существует';
    END IF;

    -- Проверяем существование таблицы posts_hot_users
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'posts_hot_users'
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Распределяем posts_hot_users по author_user_id
        PERFORM create_distributed_table('posts_hot_users', 'author_user_id', colocate_with => 'none');
        RAISE NOTICE 'posts_hot_users распределена по author_user_id';
    ELSE
        RAISE NOTICE 'Таблица posts_hot_users не существует';
    END IF;

    -- Проверяем существование таблицы dialog_messages
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'dialog_messages'
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Распределяем dialog_messages по from_user_id
        PERFORM create_distributed_table('dialog_messages', 'from_user_id');
        RAISE NOTICE 'dialog_messages распределена по from_user_id';
    ELSE
        RAISE NOTICE 'Таблица dialog_messages не существует';
    END IF;
END $$;

-- Проверяем распределение таблиц
SELECT logicalrelid, partmethod, repmodel FROM pg_dist_partition; 