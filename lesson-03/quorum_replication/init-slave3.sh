#!/bin/bash
set -e

# Ожидание доступности мастера
until pg_isready -h master -p 5432 -U postgres; do
    echo "Waiting for master to be ready..."
    sleep 1
done

# Остановка PostgreSQL
pg_ctl -D /var/lib/postgresql/data -m fast -w stop

# Очистка директории данных
rm -rf /var/lib/postgresql/data/*

# Создание базового бэкапа
pg_basebackup -h master -p 5432 -U postgres -D /var/lib/postgresql/data -P -R -X stream -S slave3_slot

# Настройка репликации
cat > /var/lib/postgresql/data/postgresql.auto.conf << EOF
primary_conninfo = 'host=master port=5432 user=postgres password=postgres application_name=slave3'
primary_slot_name = 'slave3_slot'
EOF

# Создание файла standby.signal
touch /var/lib/postgresql/data/standby.signal

# Запуск PostgreSQL
pg_ctl -D /var/lib/postgresql/data -w start
