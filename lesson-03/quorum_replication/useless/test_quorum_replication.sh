#!/bin/bash

# Скрипт для тестирования кворумной репликации PostgreSQL
# Этот скрипт выполняет следующие шаги:
# 1. Создает нагрузку на запись в базу
# 2. Убивает одну из реплик
# 3. Ждет несколько секунд и останавливает нагрузку
# 4. Выбирает самый свежий слейв и промоутит его до мастера
# 5. Переключает на него второй слейв
# 6. Возобновляет нагрузку на запись
# 7. Проверяет, есть ли потери транзакций

set -e

# Проверка наличия Python скрипта для нагрузки
if [ ! -f "load_test_replication.py" ]; then
    echo "Error: load_test_replication.py not found"
    exit 1
fi

# Даем права на выполнение скрипту нагрузки
chmod +x load_test_replication.py

# Проверяем, что контейнеры запущены
echo "Checking containers status..."
docker-compose -f docker-compose-sync-replication.yml ps

# Проверяем статус репликации
echo "Checking replication status..."
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Создаем таблицу users, если она не существует
echo "Creating users table if not exists..."
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -c "
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    second_name VARCHAR(255) NOT NULL,
    birthdate DATE NOT NULL,
    biography TEXT,
    city VARCHAR(255),
    password VARCHAR(255) NOT NULL
);"

# Шаг 1: Запускаем нагрузку на запись (100k пользователей)
echo "Starting write load test..."
/home/busybox/dev/otus-highload/venv/bin/python load_test_replication.py localhost 100000 &
LOAD_PID=$!

# Ждем 10 секунд, чтобы нагрузка началась
echo "Waiting for load test to start..."
sleep 10

# Шаг 2: Убиваем одну из реплик (db-slave3)
echo "Killing slave3..."
docker-compose -f docker-compose-sync-replication.yml stop db-slave3

# Шаг 3: Ждем несколько секунд и останавливаем нагрузку
echo "Waiting for a few seconds..."
sleep 5
echo "Stopping load test..."
kill -SIGINT $LOAD_PID
wait $LOAD_PID

# Сохраняем количество успешно записанных строк
echo "Counting users in the master database..."
USERS_MASTER=$(docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_MASTER=$(echo $USERS_MASTER | tr -d ' ')
echo "Users in master: $USERS_MASTER"

# Проверяем количество строк на слейвах
echo "Counting users in slave1..."
USERS_SLAVE1=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_SLAVE1=$(echo $USERS_SLAVE1 | tr -d ' ')
echo "Users in slave1: $USERS_SLAVE1"

echo "Counting users in slave2..."
USERS_SLAVE2=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_SLAVE2=$(echo $USERS_SLAVE2 | tr -d ' ')
echo "Users in slave2: $USERS_SLAVE2"

# Шаг 4: Выбираем самый свежий слейв (с наибольшим LSN) и промоутим его до мастера
echo "Checking LSN on slaves..."
LSN_SLAVE1=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -t -c "SELECT pg_last_wal_receive_lsn();")
LSN_SLAVE2=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -t -c "SELECT pg_last_wal_receive_lsn();")

echo "LSN on slave1: $LSN_SLAVE1"
echo "LSN on slave2: $LSN_SLAVE2"

# Определяем, какой слейв имеет больший LSN
if [[ "$LSN_SLAVE1" > "$LSN_SLAVE2" ]]; then
    NEW_MASTER="db-slave1"
    REMAINING_SLAVE="db-slave2"
    echo "Promoting slave1 to master..."
else
    NEW_MASTER="db-slave2"
    REMAINING_SLAVE="db-slave1"
    echo "Promoting slave2 to master..."
fi

# Промоутим выбранный слейв до мастера
docker-compose -f docker-compose-sync-replication.yml exec -u postgres $NEW_MASTER pg_ctl promote -D /var/lib/postgresql/data

# Ждем, пока слейв станет мастером
echo "Waiting for promotion to complete..."
sleep 5

# Шаг 5: Переключаем оставшийся слейв на новый мастер
echo "Reconfiguring remaining slave to point to new master..."
docker-compose -f docker-compose-sync-replication.yml exec $REMAINING_SLAVE bash -c "echo \"primary_conninfo = 'host=$NEW_MASTER port=5432 user=replicator password=replpass application_name=$REMAINING_SLAVE'\" > /var/lib/postgresql/data/postgresql.conf.new"
docker-compose -f docker-compose-sync-replication.yml exec $REMAINING_SLAVE bash -c "cat /var/lib/postgresql/data/postgresql.conf | grep -v primary_conninfo >> /var/lib/postgresql/data/postgresql.conf.new"
docker-compose -f docker-compose-sync-replication.yml exec $REMAINING_SLAVE bash -c "mv /var/lib/postgresql/data/postgresql.conf.new /var/lib/postgresql/data/postgresql.conf"
docker-compose -f docker-compose-sync-replication.yml restart $REMAINING_SLAVE

# Ждем, пока слейв подключится к новому мастеру
echo "Waiting for slave to connect to new master..."
sleep 10

# Шаг 6: Возобновляем нагрузку на запись на новый мастер
echo "Resuming write load test on new master..."
if [[ "$NEW_MASTER" == "db-slave1" ]]; then
    python load_test_replication.py localhost:5433 50000 &
else
    python load_test_replication.py localhost:5434 50000 &
fi
LOAD_PID=$!

# Ждем завершения нагрузки
wait $LOAD_PID

# Шаг 7: Проверяем, есть ли потери транзакций
echo "Checking for transaction losses..."

# Получаем количество строк на новом мастере
if [[ "$NEW_MASTER" == "db-slave1" ]]; then
    USERS_NEW_MASTER=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
else
    USERS_NEW_MASTER=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
fi
USERS_NEW_MASTER=$(echo $USERS_NEW_MASTER | tr -d ' ')
echo "Users in new master: $USERS_NEW_MASTER"

# Получаем количество строк на оставшемся слейве
if [[ "$REMAINING_SLAVE" == "db-slave1" ]]; then
    USERS_REMAINING_SLAVE=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
else
    USERS_REMAINING_SLAVE=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
fi
USERS_REMAINING_SLAVE=$(echo $USERS_REMAINING_SLAVE | tr -d ' ')
echo "Users in remaining slave: $USERS_REMAINING_SLAVE"

# Выводим результаты
echo "=== RESULTS ==="
echo "Initial users in master: $USERS_MASTER"
echo "Users in new master after failover: $USERS_NEW_MASTER"
echo "Users in remaining slave after failover: $USERS_REMAINING_SLAVE"

# Проверяем, есть ли потери транзакций
if [[ "$USERS_NEW_MASTER" -ge "$USERS_MASTER" ]]; then
    echo "SUCCESS: No transaction losses detected!"
else
    echo "WARNING: Possible transaction losses detected!"
    echo "Lost transactions: $(($USERS_MASTER - $USERS_NEW_MASTER))"
fi

# Проверяем согласованность между новым мастером и слейвом
if [[ "$USERS_NEW_MASTER" -eq "$USERS_REMAINING_SLAVE" ]]; then
    echo "SUCCESS: New master and slave are consistent!"
else
    echo "WARNING: New master and slave are not consistent!"
    echo "Difference: $(($USERS_NEW_MASTER - $USERS_REMAINING_SLAVE))"
fi

echo "Test completed!"
