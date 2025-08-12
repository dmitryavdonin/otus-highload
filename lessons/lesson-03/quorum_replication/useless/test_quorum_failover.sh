#!/bin/bash
set -e

# Функция для подсчета записей в таблице
count_records() {
    local host=$1
    local port=$2
    local count=$(PGPASSWORD=postgres psql -h $host -p $port -U postgres -d testdb -t -c "SELECT COUNT(*) FROM test_table;")
    echo $count | tr -d ' '
}

# Функция для вставки записей в таблицу
insert_records() {
    local host=$1
    local port=$2
    local count=$3
    local inserted=0
    
    echo "Вставка $count записей в таблицу на $host:$port..."
    
    for i in $(seq 1 $count); do
        if PGPASSWORD=postgres psql -h $host -p $port -U postgres -d testdb -c "INSERT INTO test_table (data) VALUES ('test data $i');" > /dev/null 2>&1; then
            inserted=$((inserted + 1))
        fi
    done
    
    echo "Успешно вставлено $inserted записей из $count"
    return $inserted
}

# Функция для получения LSN
get_lsn() {
    local host=$1
    local port=$2
    local lsn=$(PGPASSWORD=postgres psql -h $host -p $port -U postgres -t -c "SELECT pg_current_wal_lsn();" 2>/dev/null || PGPASSWORD=postgres psql -h $host -p $port -U postgres -t -c "SELECT pg_last_wal_receive_lsn();" 2>/dev/null)
    echo $lsn | tr -d ' '
}

# Функция для промоута слейва до мастера
promote_slave() {
    local container=$1
    echo "Промоут слейва $container до мастера..."
    docker exec -u postgres $container pg_ctl promote -D /var/lib/postgresql/data
}

# Функция для переключения слейва на новый мастер
switch_slave_to_new_master() {
    local slave_container=$1
    local new_master_host=$2
    echo "Переключение слейва $slave_container на новый мастер $new_master_host..."
    docker exec -u postgres $slave_container psql -c "ALTER SYSTEM SET primary_conninfo = 'host=$new_master_host port=5432 user=postgres password=postgres application_name=$slave_container';"
    docker exec -u postgres $slave_container pg_ctl reload -D /var/lib/postgresql/data
}

# Шаг 1: Проверка статуса репликации
echo "Шаг 1: Проверка статуса репликации..."
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"

# Шаг 2: Подсчет начального количества записей
echo "Шаг 2: Подсчет начального количества записей..."
initial_count=$(count_records localhost 5432)
echo "Начальное количество записей: $initial_count"

# Шаг 3: Создание нагрузки на запись
echo "Шаг 3: Создание нагрузки на запись..."
insert_records localhost 5432 100
inserted_before_failure=$?
echo "Вставлено записей до сбоя: $inserted_before_failure"

# Шаг 4: Подсчет записей после вставки
echo "Шаг 4: Подсчет записей после вставки..."
count_after_insert=$(count_records localhost 5432)
echo "Количество записей после вставки: $count_after_insert"

# Шаг 5: Убиваем одну из реплик (slave3)
echo "Шаг 5: Убиваем одну из реплик (slave3)..."
docker stop pg-slave3

# Шаг 6: Создаем еще нагрузку на запись
echo "Шаг 6: Создаем еще нагрузку на запись..."
insert_records localhost 5432 100
inserted_after_failure=$?
echo "Вставлено записей после сбоя: $inserted_after_failure"

# Шаг 7: Подсчет записей после второй вставки
echo "Шаг 7: Подсчет записей после второй вставки..."
count_after_second_insert=$(count_records localhost 5432)
echo "Количество записей после второй вставки: $count_after_second_insert"

# Шаг 8: Убиваем мастер
echo "Шаг 8: Убиваем мастер..."
docker stop pg-master

# Шаг 9: Выбираем самый свежий слейв
echo "Шаг 9: Выбираем самый свежий слейв..."
lsn_slave1=$(get_lsn localhost 5433)
lsn_slave2=$(get_lsn localhost 5434)

echo "LSN на slave1: $lsn_slave1"
echo "LSN на slave2: $lsn_slave2"

if [[ "$lsn_slave1" > "$lsn_slave2" ]]; then
    new_master="pg-slave1"
    new_master_host="slave1"
    new_master_port=5433
    remaining_slave="pg-slave2"
    echo "slave1 имеет больший LSN, промоутим его до мастера"
else
    new_master="pg-slave2"
    new_master_host="slave2"
    new_master_port=5434
    remaining_slave="pg-slave1"
    echo "slave2 имеет больший LSN, промоутим его до мастера"
fi

# Шаг 10: Промоутим выбранный слейв до мастера
echo "Шаг 10: Промоутим $new_master до мастера..."
promote_slave $new_master

# Шаг 11: Ждем, пока слейв станет мастером
echo "Шаг 11: Ожидание завершения промоута..."
sleep 5

# Шаг 11.1: Обновляем настройки синхронной репликации на новом мастере
echo "Шаг 11.1: Обновляем настройки синхронной репликации на новом мастере..."
if [[ "$new_master" == "pg-slave1" ]]; then
    docker exec -u postgres $new_master psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 (slave2)';"
else
    docker exec -u postgres $new_master psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 (slave1)';"
fi
docker exec -u postgres $new_master pg_ctl reload -D /var/lib/postgresql/data

# Шаг 12: Переключаем оставшийся слейв на новый мастер
echo "Шаг 12: Переключаем $remaining_slave на новый мастер $new_master_host..."
switch_slave_to_new_master $remaining_slave $new_master_host

# Шаг 13: Ждем, пока слейв подключится к новому мастеру
echo "Шаг 13: Ожидание подключения слейва к новому мастеру..."
sleep 5

# Шаг 14: Подсчет записей на новом мастере
echo "Шаг 14: Подсчет записей на новом мастере..."
count_on_new_master=$(count_records localhost $new_master_port)
echo "Количество записей на новом мастере: $count_on_new_master"

# Шаг 15: Проверка потери транзакций
echo "Шаг 15: Проверка потери транзакций..."
expected_count=$((initial_count + inserted_before_failure + inserted_after_failure))
echo "Ожидаемое количество записей: $expected_count"
echo "Фактическое количество записей на новом мастере: $count_on_new_master"

if [[ "$count_on_new_master" -eq "$expected_count" ]]; then
    echo "УСПЕХ: Потерь транзакций не обнаружено!"
else
    echo "ВНИМАНИЕ: Обнаружены потери транзакций!"
    echo "Потеряно транзакций: $(($expected_count - $count_on_new_master))"
fi

echo "Тест завершен!"
