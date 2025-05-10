#!/bin/bash
set -e

echo "==== Тестирование шардирования с Citus ===="

# Проверка доступности координатора
echo "Проверка доступности координатора..."
if ! docker-compose exec citus-coordinator pg_isready -U postgres -q; then
    echo "Ошибка: координатор недоступен, проверьте состояние сервисов."
    exit 1
fi

# Проверка доступности рабочих узлов
echo "Проверка доступности рабочих узлов..."
for worker in citus-worker-1 citus-worker-2 citus-worker-3; do
    if ! docker-compose exec $worker pg_isready -U postgres -q; then
        echo "Ошибка: узел $worker недоступен, проверьте состояние сервисов."
        exit 1
    fi
    echo "Узел $worker доступен."
done

echo "Все узлы кластера доступны."

# Проверка статуса кластера
echo -e "\nСтатус кластера Citus:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT nodename, nodeport, noderole, isactive 
    FROM pg_dist_node;
"

# Проверка наличия таблиц и их распределения
echo -e "\nПроверка распределения таблиц:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT logicalrelid::regclass, partmethod, partkey, repmodel
    FROM pg_dist_partition
    ORDER BY logicalrelid;
"

# Тест 1: Создание тестовых данных
echo -e "\nТест 1: Создание тестовых пользователей..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    -- Удаление существующих тестовых данных (если есть)
    DELETE FROM users WHERE first_name LIKE 'Test%';
    
    -- Создание тестовых пользователей
    INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password, created_at)
    SELECT 
        gen_random_uuid(), 
        'Test User ' || i, 
        'Surname ' || i,
        CURRENT_DATE - (20 * 365 + i)::integer,
        'Test biography ' || i,
        'City ' || (i % 10),
        'password' || i,
        CURRENT_TIMESTAMP - (i || ' hours')::interval
    FROM generate_series(1, 100) i;
"

# Тест 2: Проверка распределения данных по шардам
echo -e "\nТест 2: Проверка распределения данных по шардам..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    -- Проверка количества пользователей на каждом узле
    SELECT nodename, result as user_count 
    FROM run_command_on_workers('SELECT count(*) FROM users WHERE first_name LIKE ''Test%''');
"

# Тест 3: Создание дружеских связей между тестовыми пользователями
echo -e "\nТест 3: Создание связей между пользователями..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    -- Удаление существующих связей
    DELETE FROM friends 
    WHERE user_id IN (SELECT id FROM users WHERE first_name LIKE 'Test%')
    OR friend_id IN (SELECT id FROM users WHERE first_name LIKE 'Test%');
    
    -- Создание новых дружеских связей
    WITH test_users AS (
        SELECT id FROM users WHERE first_name LIKE 'Test%' LIMIT 100
    )
    INSERT INTO friends (user_id, friend_id, created_at)
    SELECT 
        u1.id, 
        u2.id, 
        CURRENT_TIMESTAMP
    FROM 
        (SELECT id FROM test_users ORDER BY id LIMIT 50) u1
    CROSS JOIN 
        (SELECT id FROM test_users ORDER BY id DESC LIMIT 50) u2
    WHERE 
        u1.id != u2.id
    LIMIT 200;
"

# Тест 4: Проверка распределения связей по шардам
echo -e "\nТест 4: Проверка распределения связей по шардам..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    -- Проверка количества связей на каждом узле
    SELECT nodename, result as friend_count
    FROM run_command_on_workers('SELECT count(*) FROM friends WHERE user_id IN (SELECT id FROM users WHERE first_name LIKE ''Test%'')');
"

# Тест 5: Тест производительности основных запросов
echo -e "\nТест 5: Тест производительности запросов..."

echo "-- Тест 5.1: Поиск пользователей по имени"
start_time=$(date +%s.%N)
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*) FROM users WHERE first_name LIKE 'Test%';
"
end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc)
echo "Время выполнения: $duration секунд"

echo "-- Тест 5.2: Поиск друзей конкретного пользователя"
start_time=$(date +%s.%N)
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*) 
    FROM friends 
    WHERE user_id = (SELECT id FROM users WHERE first_name LIKE 'Test%' LIMIT 1);
"
end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc)
echo "Время выполнения: $duration секунд"

echo "-- Тест 5.3: JOIN между пользователями и друзьями"
start_time=$(date +%s.%N)
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*)
    FROM users u
    JOIN friends f ON u.id = f.user_id
    WHERE u.first_name LIKE 'Test%';
"
end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc)
echo "Время выполнения: $duration секунд"

# Проверка размера таблиц на координаторе
echo -e "\nПроверка размера таблиц на координаторе:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT
        c.relname as table_name,
        pg_size_pretty(pg_table_size(c.oid)) as table_size,
        pg_size_pretty(pg_indexes_size(c.oid)) as index_size,
        pg_size_pretty(pg_total_relation_size(c.oid)) as total_size
    FROM
        pg_class c
    LEFT JOIN
        pg_namespace n ON (n.oid = c.relnamespace)
    WHERE
        n.nspname NOT IN ('pg_catalog', 'information_schema') AND
        c.relkind = 'r'
    ORDER BY
        pg_total_relation_size(c.oid) DESC;
"

echo -e "\n==== Тестирование шардирования завершено успешно ====" 