#!/bin/bash

# Скрипт для тестирования кворумной синхронной репликации PostgreSQL
# Этот скрипт выполняет следующие шаги:
# 1. Создает нагрузку на запись в базу
# 2. Убивает одну из реплик
# 3. Заканчивает нагрузку на запись
# 4. Выбирает самый свежий слейв и промоутит его до мастера
# 5. Переключает на него второй слейв
# 6. Проверяет, есть ли потери транзакций

set -e

# Проверка наличия Python скрипта для нагрузки
if [ ! -f "load_test_quorum.py" ]; then
    echo "Ошибка: load_test_quorum.py не найден"
    exit 1
fi

# Даем права на выполнение скрипту нагрузки
chmod +x load_test_quorum.py

# Проверяем, что контейнеры запущены
echo "Проверка статуса контейнеров..."
docker-compose -f docker-compose-quorum.yml ps

# Проверяем статус репликации
echo "Проверка статуса репликации..."
docker exec pg-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"

# Шаг 1: Запускаем нагрузку на запись (10000 записей)
echo "Запуск нагрузки на запись..."
python3 load_test_quorum.py localhost 5432 10000 &
LOAD_PID=$!

# Ждем 5 секунд, чтобы нагрузка началась
echo "Ожидание начала нагрузки..."
sleep 5

# Шаг 2: Убиваем одну из реплик (slave3)
echo "Остановка slave3..."
docker stop pg-slave3

# Шаг 3: Ждем несколько секунд и останавливаем нагрузку
echo "Ожидание..."
sleep 5
echo "Остановка нагрузки..."
kill -SIGINT $LOAD_PID
wait $LOAD_PID

# Сохраняем количество успешно записанных строк
echo "Подсчет записей в мастере..."
RECORDS_MASTER=$(docker exec pg-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_MASTER=$(echo $RECORDS_MASTER | tr -d ' ')
echo "Записей в мастере: $RECORDS_MASTER"

# Проверяем количество строк на слейвах
echo "Подсчет записей в slave1..."
RECORDS_SLAVE1=$(docker exec pg-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_SLAVE1=$(echo $RECORDS_SLAVE1 | tr -d ' ')
echo "Записей в slave1: $RECORDS_SLAVE1"

echo "Подсчет записей в slave2..."
RECORDS_SLAVE2=$(docker exec pg-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_SLAVE2=$(echo $RECORDS_SLAVE2 | tr -d ' ')
echo "Записей в slave2: $RECORDS_SLAVE2"

# Шаг 4: Выбираем самый свежий слейв (с наибольшим LSN) и промоутим его до мастера
echo "Проверка LSN на слейвах..."
LSN_SLAVE1=$(docker exec pg-slave1 psql -U postgres -t -c "SELECT pg_last_wal_receive_lsn();")
LSN_SLAVE2=$(docker exec pg-slave2 psql -U postgres -t -c "SELECT pg_last_wal_receive_lsn();")

echo "LSN на slave1: $LSN_SLAVE1"
echo "LSN на slave2: $LSN_SLAVE2"

# Определяем, какой слейв имеет больший LSN
if [[ "$LSN_SLAVE1" > "$LSN_SLAVE2" ]]; then
    NEW_MASTER="pg-slave1"
    NEW_MASTER_PORT="5433"
    REMAINING_SLAVE="pg-slave2"
    echo "Промоутим slave1 до мастера..."
else
    NEW_MASTER="pg-slave2"
    NEW_MASTER_PORT="5434"
    REMAINING_SLAVE="pg-slave1"
    echo "Промоутим slave2 до мастера..."
fi

# Промоутим выбранный слейв до мастера
docker exec -u postgres $NEW_MASTER pg_ctl promote -D /var/lib/postgresql/data

# Ждем, пока слейв станет мастером
echo "Ожидание завершения промоута..."
sleep 5

# Шаг 5: Переключаем оставшийся слейв на новый мастер
echo "Переконфигурация оставшегося слейва для подключения к новому мастеру..."
docker exec $REMAINING_SLAVE bash -c "echo \"primary_conninfo = 'host=$NEW_MASTER port=5432 user=replicator password=replpass application_name=$REMAINING_SLAVE'\" > /var/lib/postgresql/data/postgresql.auto.conf"
docker exec $REMAINING_SLAVE bash -c "pg_ctl restart -D /var/lib/postgresql/data"

# Ждем, пока слейв подключится к новому мастеру
echo "Ожидание подключения слейва к новому мастеру..."
sleep 10

# Шаг 6: Проверяем, есть ли потери транзакций
echo "Проверка потерь транзакций..."

# Получаем количество строк на новом мастере
RECORDS_NEW_MASTER=$(docker exec $NEW_MASTER psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_NEW_MASTER=$(echo $RECORDS_NEW_MASTER | tr -d ' ')
echo "Записей в новом мастере: $RECORDS_NEW_MASTER"

# Получаем количество строк на оставшемся слейве
RECORDS_REMAINING_SLAVE=$(docker exec $REMAINING_SLAVE psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_REMAINING_SLAVE=$(echo $RECORDS_REMAINING_SLAVE | tr -d ' ')
echo "Записей в оставшемся слейве: $RECORDS_REMAINING_SLAVE"

# Выводим результаты
echo "=== РЕЗУЛЬТАТЫ ==="
echo "Исходное количество записей в мастере: $RECORDS_MASTER"
echo "Количество записей в новом мастере после переключения: $RECORDS_NEW_MASTER"
echo "Количество записей в оставшемся слейве после переключения: $RECORDS_REMAINING_SLAVE"

# Проверяем, есть ли потери транзакций
if [[ "$RECORDS_NEW_MASTER" -eq "$RECORDS_MASTER" ]]; then
    echo "УСПЕХ: Потерь транзакций не обнаружено!"
else
    echo "ВНИМАНИЕ: Обнаружены возможные потери транзакций!"
    echo "Потеряно транзакций: $(($RECORDS_MASTER - $RECORDS_NEW_MASTER))"
fi

# Проверяем согласованность между новым мастером и слейвом
if [[ "$RECORDS_NEW_MASTER" -eq "$RECORDS_REMAINING_SLAVE" ]]; then
    echo "УСПЕХ: Новый мастер и слейв согласованы!"
else
    echo "ВНИМАНИЕ: Новый мастер и слейв не согласованы!"
    echo "Разница: $(($RECORDS_NEW_MASTER - $RECORDS_REMAINING_SLAVE))"
fi

echo "Тест завершен!"
