#!/bin/bash
set -e

# Останавливаем PostgreSQL
pg_ctl -D "$PGDATA" -m fast -w stop

# Очищаем директорию данных
rm -rf "$PGDATA"/*

# Создаем базовую резервную копию с мастера
PGPASSWORD=replpass pg_basebackup -h db-master -p 5432 -U replicator -D "$PGDATA" -P -v -R -X stream -C -S "$(hostname | tr '-' '_')_slot"

# Настраиваем параметры для репликации
cat >> "$PGDATA"/postgresql.conf << EOF
listen_addresses = '*'
hot_standby = on
EOF

# Запускаем PostgreSQL
pg_ctl -D "$PGDATA" -w start
