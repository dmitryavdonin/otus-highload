#!/bin/bash
set -e

# Создаем пользователя для репликации
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replpass';
    ALTER USER replicator WITH PASSWORD 'replpass';
EOSQL

# Настраиваем параметры для репликации
cat >> /var/lib/postgresql/data/postgresql.conf << EOF
listen_addresses = '*'
wal_level = logical
max_wal_senders = 10
max_replication_slots = 10
synchronous_commit = on
synchronous_standby_names = 'FIRST 2 (db_slave1, db_slave2, db_slave3)'
EOF

# Разрешаем подключение для репликации
cat >> /var/lib/postgresql/data/pg_hba.conf << EOF
host replication replicator all md5
host all postgres all md5
EOF

# Создаем таблицу users
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        first_name VARCHAR(255) NOT NULL,
        second_name VARCHAR(255) NOT NULL,
        birthdate DATE NOT NULL,
        biography TEXT,
        city VARCHAR(255),
        password VARCHAR(255) NOT NULL
    );
EOSQL
