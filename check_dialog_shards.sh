#!/bin/bash
set -e

echo "==== Проверка распределения сообщений диалогов между шардами ===="

# Проверка наличия сообщений в таблице dialog_messages
echo "Проверка наличия сообщений в таблице dialog_messages..."
MESSAGE_COUNT=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "
    SELECT COUNT(*) FROM dialog_messages;
")

MESSAGE_COUNT=$(echo $MESSAGE_COUNT | tr -d '[:space:]')

if [ "$MESSAGE_COUNT" -eq "0" ]; then
    echo "Ошибка: в таблице dialog_messages нет сообщений!"
    echo "Возможно, тест test_dialogs.py не был запущен или произошла ошибка."
    exit 1
else
    echo "Обнаружено $MESSAGE_COUNT сообщений в таблице dialog_messages."
fi

# Проверка шардирования и распределения сообщений
echo -e "\nРаспределение сообщений на узле-координаторе:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT 
        to_char(created_at, 'YYYY-MM-DD') as date,
        COUNT(*) as message_count
    FROM 
        dialog_messages
    GROUP BY 
        date
    ORDER BY 
        date;
"

# Для reference-таблицы users проверяем наличие пользователей на всех узлах
echo -e "\nПроверка наличия пользователей на всех узлах (users как reference-таблица):"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT nodename, result as user_count
    FROM run_command_on_workers('
        SELECT COUNT(*) FROM users;
    ');
"

# Проверка конфигурации таблицы dialog_messages
echo -e "\nАнализ конфигурации таблицы dialog_messages:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT 
        logicalrelid, 
        partmethod, 
        partkey, 
        colocationid, 
        repmodel, 
        autoconverted
    FROM 
        pg_dist_partition 
    WHERE 
        logicalrelid = 'dialog_messages'::regclass;
"

echo -e "\nРаспределение диалогов по пользователям:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    WITH user_stats AS (
        SELECT 
            u.id,
            u.first_name || ' ' || u.second_name as user_name,
            (SELECT COUNT(*) FROM dialog_messages WHERE from_user_id = u.id) as sent_messages,
            (SELECT COUNT(*) FROM dialog_messages WHERE to_user_id = u.id) as received_messages
        FROM 
            users u
        WHERE 
            (SELECT COUNT(*) FROM dialog_messages WHERE from_user_id = u.id OR to_user_id = u.id) > 0
    )
    SELECT 
        user_name,
        sent_messages,
        received_messages,
        sent_messages + received_messages as total_messages
    FROM 
        user_stats
    ORDER BY 
        total_messages DESC
    LIMIT 10;
"

echo -e "\nТоп диалогов между пользователями:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT 
        u1.first_name || ' ' || u1.second_name as sender,
        u2.first_name || ' ' || u2.second_name as receiver,
        COUNT(*) as message_count
    FROM 
        dialog_messages dm
    JOIN 
        users u1 ON dm.from_user_id = u1.id
    JOIN 
        users u2 ON dm.to_user_id = u2.id
    GROUP BY 
        sender, receiver
    ORDER BY 
        message_count DESC
    LIMIT 10;
"

echo -e "\n==== Проверка распределения сообщений завершена ====" 