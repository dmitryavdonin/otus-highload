#!/bin/bash
set -e

# Настройка PostgreSQL для мастер-сервера с репликацией
echo "Настройка мастер-сервера PostgreSQL..."

# Ожидание запуска PostgreSQL
sleep 10

# Создание пользователя для репликации
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replicator_password';
    SELECT pg_create_physical_replication_slot('replica_slot_1');
    SELECT pg_create_physical_replication_slot('replica_slot_2');
EOSQL

echo "Мастер-сервер настроен успешно!" 