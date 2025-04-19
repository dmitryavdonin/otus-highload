#!/bin/bash
set -e

# Настройка PostgreSQL для прослушивания всех интерфейсов
echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf"

# Настройка WAL и репликации
cat >> "$PGDATA/postgresql.conf" << EOF
# Настройки репликации
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
wal_keep_size = 1GB
hot_standby = on

# Настройки синхронной репликации
synchronous_commit = on
synchronous_standby_names = 'ANY 2 (slave1, slave2, slave3)'
EOF

# Настройка доступа для репликации
cat >> "$PGDATA/pg_hba.conf" << EOF
# Разрешить репликацию для пользователя replicator
host replication replicator all md5
host all all all md5
EOF

# Создание пользователя для репликации
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres << EOF
CREATE USER replicator WITH REPLICATION PASSWORD 'replpass';
SELECT * FROM pg_create_physical_replication_slot('slave1_slot');
SELECT * FROM pg_create_physical_replication_slot('slave2_slot');
SELECT * FROM pg_create_physical_replication_slot('slave3_slot');
EOF

# Создание тестовой таблицы
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOF
CREATE TABLE IF NOT EXISTS test_replication (
    id SERIAL PRIMARY KEY,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

# Перезагрузка конфигурации PostgreSQL
pg_ctl reload
