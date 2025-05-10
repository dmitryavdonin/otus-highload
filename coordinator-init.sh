#!/bin/bash
set -e

# Включение расширения Citus
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS citus;
    SELECT citus_set_coordinator_host('citus-coordinator', 5432);
    
    -- Установка оптимального количества шардов (32 шарда на каждый узел)
    -- Для трех рабочих узлов = 32 * 3 = 96
    SET citus.shard_count = 96;
    
    -- Настройка сетевых параметров
    ALTER SYSTEM SET citus.node_connection_timeout = 10000;  -- 10 секунд
    
    -- Настройка репликации шардов
    -- ВАЖНО: Установка shard_replication_factor = 1 необходима для поддержки внешних ключей
    ALTER SYSTEM SET citus.shard_replication_factor = 1;
    
    -- Применение изменений
    SELECT pg_reload_conf();
EOSQL

# Дождемся завершения скрипта инициализации и создания пользователей и БД
sleep 10

# Добавление рабочих узлов в кластер
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT * from citus_add_node('citus-worker-1', 5432);
    SELECT * from citus_add_node('citus-worker-2', 5432);
    SELECT * from citus_add_node('citus-worker-3', 5432);
EOSQL

# Создаем схему базы данных из schema.sql
echo "Создание схемы базы данных из schema.sql..."
if [ -f /docker-entrypoint-initdb.d/schema.sql ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/schema.sql
    echo "Схема базы данных успешно создана."
else
    echo "ОШИБКА: Файл schema.sql не найден!"
    exit 1
fi

# Дистрибуция таблиц
echo "Создание распределенных таблиц..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Мы выбираем новую стратегию с использованием reference-таблиц для сохранения целостности данных
    
    -- Создаем таблицу users как reference table для сохранения внешних ключей
    -- Это компромисс, который жертвует шардированием users ради сохранения внешних ключей
    SELECT create_reference_table('users');
    
    -- Остальные таблицы сделаем локальными (не распределенными), так как это проще,
    -- чем пытаться правильно настроить внешние ключи с ограничениями Citus
    -- В реальной ситуации можно было бы изменить схему БД для лучшей поддержки шардирования
    
    -- Альтернативный вариант - активно использовать кеширование в Redis
    -- для уменьшения нагрузки на базу данных
    
    -- Если бы мы изменяли схему таблиц:
    -- 1. Таблицу auth_tokens можно модифицировать, чтобы PRIMARY KEY включал user_id
    -- 2. Таблицу friends можно было бы разделить на две односторонние связи
    -- Но это требует изменения схемы, что не входит в наши текущие задачи
    
    -- Создадим дополнительные индексы для улучшения производительности
    CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id);
    CREATE INDEX IF NOT EXISTS idx_dialog_messages_to_user ON dialog_messages(to_user_id);
    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
    CREATE INDEX IF NOT EXISTS idx_friends_friend_id ON friends(friend_id);
    
    -- Включаем параллельные запросы для улучшения производительности
    ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
    ALTER SYSTEM SET max_parallel_workers = 8;
    SELECT pg_reload_conf();
EOSQL

echo "Инициализация координатора Citus завершена" 