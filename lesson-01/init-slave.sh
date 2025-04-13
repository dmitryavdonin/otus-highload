#!/bin/bash

set -e

# Ждем, пока мастер будет готов
until pg_isready -h db-master -p 5432 -U postgres; do
    echo "Waiting for master to be ready..."
    sleep 1
done

# Настраиваем права на .pgpass
chmod 0600 /var/lib/postgresql/.pgpass
chown postgres:postgres /var/lib/postgresql/.pgpass

# Проверяем, есть ли файл standby.signal
if [ ! -f /var/lib/postgresql/data/standby.signal ]; then
    echo "Initializing slave..."
    
    # Если есть данные, удаляем их
    if [ -n "$(ls -A /var/lib/postgresql/data 2>/dev/null)" ]; then
        echo "Cleaning up existing data directory..."
        rm -rf /var/lib/postgresql/data/*
    fi
    
    # Выполняем pg_basebackup
    PGPASSFILE=/var/lib/postgresql/.pgpass pg_basebackup -h db-master -p 5432 -U replicator -D /var/lib/postgresql/data -P -v -R
    
    # Настраиваем конфигурацию для репликации
    echo "primary_conninfo = 'host=db-master port=5432 user=replicator password=replpass application_name=${SLAVE_NAME}'" > /var/lib/postgresql/data/postgresql.conf
    echo "hot_standby = on" >> /var/lib/postgresql/data/postgresql.conf
    touch /var/lib/postgresql/data/standby.signal
else
    echo "Slave already initialized, skipping initialization..."
fi

# Запускаем PostgreSQL
exec postgres 