#!/bin/bash
set -e

# Функция для ожидания доступности PostgreSQL
wait_for_postgres() {
    local host=$1
    local port=$2
    echo "Ожидание доступности PostgreSQL на $host:$port..."
    until PGPASSWORD=postgres psql -h $host -p $port -U postgres -c "SELECT 1;" > /dev/null 2>&1; do
        echo "Ожидание PostgreSQL на $host:$port..."
        sleep 1
    done
    echo "PostgreSQL на $host:$port доступен!"
}

# Функция для создания слота репликации
create_replication_slot() {
    local host=$1
    local port=$2
    local slot_name=$3
    echo "Создание слота репликации $slot_name на $host:$port..."
    PGPASSWORD=postgres psql -h $host -p $port -U postgres -c "SELECT * FROM pg_create_physical_replication_slot('$slot_name');"
}

# Функция для настройки слейва
setup_slave() {
    local container=$1
    local master_host=$2
    local application_name=$3
    local slot_name=$4
    
    echo "Настройка $container как слейва для $master_host..."
    
    # Запуск контейнера, если он остановлен
    docker start $container || true
    
    # Ожидание запуска контейнера
    sleep 5
    
    # Остановка PostgreSQL
    docker exec -u postgres $container pg_ctl -D /var/lib/postgresql/data -m fast -w stop || true
    
    # Очистка директории данных
    docker exec -u postgres $container bash -c "rm -rf /var/lib/postgresql/data/*"
    
    # Создание базового бэкапа с нового мастера
    docker exec -u postgres $container pg_basebackup -h $master_host -p 5432 -U postgres -D /var/lib/postgresql/data -P -R -X stream -S $slot_name
    
    # Настройка репликации
    docker exec -u postgres $container bash -c "cat > /var/lib/postgresql/data/postgresql.auto.conf << EOF
primary_conninfo = 'host=$master_host port=5432 user=postgres password=postgres application_name=$application_name'
primary_slot_name = '$slot_name'
EOF"
    
    # Создание файла standby.signal
    docker exec -u postgres $container touch /var/lib/postgresql/data/standby.signal
    
    # Запуск PostgreSQL
    docker exec -u postgres $container pg_ctl -D /var/lib/postgresql/data -w start
}

# Определение текущего мастера
echo "Определение текущего мастера..."
if docker exec pg-slave1 pg_isready -h localhost -p 5432 > /dev/null 2>&1 && \
   docker exec pg-slave1 psql -U postgres -c "SELECT pg_is_in_recovery();" -t | grep -q f; then
    current_master="pg-slave1"
    current_master_host="slave1"
    current_master_port=5433
    echo "Текущий мастер: $current_master"
elif docker exec pg-slave2 pg_isready -h localhost -p 5432 > /dev/null 2>&1 && \
     docker exec pg-slave2 psql -U postgres -c "SELECT pg_is_in_recovery();" -t | grep -q f; then
    current_master="pg-slave2"
    current_master_host="slave2"
    current_master_port=5434
    echo "Текущий мастер: $current_master"
else
    echo "Не удалось определить текущий мастер. Убедитесь, что хотя бы один из слейвов был промоутирован до мастера."
    exit 1
fi

# Шаг 1: Создание слотов репликации на текущем мастере для отсутствующих слейвов
echo "Шаг 1: Создание слотов репликации на текущем мастере..."

# Проверка существующих слотов
existing_slots=$(docker exec $current_master psql -U postgres -c "SELECT slot_name FROM pg_replication_slots;" -t | tr -d ' ')

# Создание слота для старого мастера, если его нет
if ! echo "$existing_slots" | grep -q "master_slot"; then
    create_replication_slot localhost $current_master_port "master_slot"
fi

# Создание слота для slave3, если его нет
if ! echo "$existing_slots" | grep -q "slave3_slot"; then
    create_replication_slot localhost $current_master_port "slave3_slot"
fi

# Шаг 2: Восстановление старого мастера как слейва
echo "Шаг 2: Восстановление старого мастера как слейва..."
setup_slave "pg-master" $current_master_host "master" "master_slot"

# Шаг 3: Восстановление slave3
echo "Шаг 3: Восстановление slave3..."
setup_slave "pg-slave3" $current_master_host "slave3" "slave3_slot"

# Шаг 4: Настройка кворумной репликации на новом мастере
echo "Шаг 4: Настройка кворумной репликации на новом мастере..."
if [ "$current_master" == "pg-slave1" ]; then
    docker exec -u postgres $current_master psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 2 (master, slave2, slave3)';"
elif [ "$current_master" == "pg-slave2" ]; then
    docker exec -u postgres $current_master psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 2 (master, slave1, slave3)';"
fi

# Проверяем, что настройка применилась
docker exec -u postgres $current_master psql -c "SHOW synchronous_standby_names;"

docker exec -u postgres $current_master pg_ctl reload -D /var/lib/postgresql/data

# Шаг 5: Проверка статуса репликации
echo "Шаг 5: Проверка статуса репликации..."
sleep 5  # Даем время на установление репликации
docker exec $current_master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"

echo "Восстановление полного кластера завершено!"
