#!/bin/bash
set -e

echo "Инициализация слейва PostgreSQL..."

# Ожидание готовности мастера
echo "Ожидание готовности мастера..."
while ! pg_isready -h postgres-master -U postgres -d social_network; do 
    echo "Мастер еще не готов, ждем..."
    sleep 5
done
echo "Мастер готов!"

# Определяем номер слейва из имени хоста
if [[ $POSTGRES_SERVER_NAME == *"slave1"* ]]; then
    SLOT_NAME="replica_slot_1"
elif [[ $POSTGRES_SERVER_NAME == *"slave2"* ]]; then
    SLOT_NAME="replica_slot_2"
else
    echo "Неизвестное имя сервера: $POSTGRES_SERVER_NAME"
    exit 1
fi

# Останавливаем PostgreSQL если он запущен
pg_ctl stop -D /var/lib/postgresql/data -m fast || true

# Очищаем директорию данных только если там нет standby.signal
if [ ! -f /var/lib/postgresql/data/standby.signal ]; then
    echo "Первичная настройка слейва - создаем базовую копию"
    rm -rf /var/lib/postgresql/data/*
    
    # Создаем базовую копию с мастера
    PGPASSWORD=replicator_password pg_basebackup -h postgres-master -D /var/lib/postgresql/data -U replicator -v -P -W
    
    # Создаем файл восстановления
    cat > /var/lib/postgresql/data/postgresql.auto.conf <<EOF
# Конфигурация репликации
primary_conninfo = 'host=postgres-master port=5432 user=replicator password=replicator_password'
primary_slot_name = '$SLOT_NAME'
EOF
    
    # Создаем standby.signal для указания что это слейв
    touch /var/lib/postgresql/data/standby.signal
    
    echo "Слейв $POSTGRES_SERVER_NAME настроен с слотом $SLOT_NAME"
else
    echo "Слейв уже настроен, пропускаем инициализацию"
fi 