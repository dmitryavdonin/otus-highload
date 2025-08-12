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
echo -e "\nРаспределение сообщений по датам:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
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
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT nodename, result as user_count
    FROM run_command_on_workers('
        SELECT COUNT(*) FROM users;
    ');
"

# Проверка конфигурации таблицы dialog_messages
echo -e "\nАнализ конфигурации таблицы dialog_messages:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT 
        logicalrelid, 
        partmethod, 
        partkey, 
        colocationid, 
        repmodel
    FROM 
        pg_dist_partition 
    WHERE 
        logicalrelid = 'dialog_messages'::regclass;
"

# Проверка распределения сообщений по шардам
echo -e "\nРаспределение сообщений по шардам:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT 
        pds.shardid, 
        pn.nodename,
        pdsp.shardstate,
        pdsp.shardlength
    FROM 
        pg_dist_shard pds
    JOIN 
        pg_dist_placement pdsp ON pds.shardid = pdsp.shardid
    JOIN 
        pg_dist_node pn ON pdsp.groupid = pn.groupid
    WHERE 
        pds.logicalrelid = 'dialog_messages'::regclass
    ORDER BY 
        pds.shardid;
"

# Проверка распределения сообщений по узлам
echo -e "\nКоличество сообщений на разных узлах:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT 
        nodename, 
        result AS message_count
    FROM 
        run_command_on_workers('SELECT COUNT(*) FROM dialog_messages');
"

# Проверка топ отправителей (без соединения с users)
echo -e "\nТоп отправителей сообщений:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT 
        from_user_id,
        COUNT(*) as sent_count
    FROM 
        dialog_messages
    GROUP BY 
        from_user_id
    ORDER BY 
        sent_count DESC
    LIMIT 5;
"

# Проверка топ получателей (без соединения с users)
echo -e "\nТоп получателей сообщений:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT 
        to_user_id,
        COUNT(*) as received_count
    FROM 
        dialog_messages
    GROUP BY 
        to_user_id
    ORDER BY 
        received_count DESC
    LIMIT 5;
"

echo -e "\n==== Проверка распределения сообщений завершена ====" 