#!/bin/bash
set -e

# Настройка PostgreSQL для прослушивания всех интерфейсов
cat >> /var/lib/postgresql/data/postgresql.conf << EOF
listen_addresses = '*'
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
synchronous_commit = on
synchronous_standby_names = 'ANY 2 (slave1, slave2, slave3)'
EOF

# Настройка доступа для репликации
cat >> /var/lib/postgresql/data/pg_hba.conf << EOF
host replication postgres all md5
host all postgres all md5
EOF

# Создание тестовой таблицы
psql -U postgres -d testdb << EOF
CREATE TABLE test_table (id SERIAL PRIMARY KEY, data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
EOF

# Создание слотов репликации
psql -U postgres << EOF
SELECT pg_create_physical_replication_slot('slave1_slot');
SELECT pg_create_physical_replication_slot('slave2_slot');
SELECT pg_create_physical_replication_slot('slave3_slot');
EOF
