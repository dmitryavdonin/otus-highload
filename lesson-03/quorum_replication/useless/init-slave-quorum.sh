#!/bin/bash
set -e

# Остановка PostgreSQL, если он запущен
if pg_ctl status -D "$PGDATA" > /dev/null 2>&1; then
    pg_ctl stop -D "$PGDATA" -m fast
    while pg_ctl status -D "$PGDATA" > /dev/null 2>&1; do
        sleep 1
    done
fi

# Ожидание доступности мастера
until PGPASSWORD=postgres psql -h $MASTER_HOST -U postgres -d postgres -c '\q'; do
    >&2 echo "Мастер недоступен - ожидание..."
    sleep 1
done

>&2 echo "Мастер доступен - выполнение команд"

# Удаление существующего каталога данных
rm -rf "$PGDATA"/*

# Выполнение базового бэкапа
PGPASSWORD=replpass pg_basebackup -h $MASTER_HOST -U replicator -p 5432 -D "$PGDATA" -Fp -Xs -P -R \
    -C -S "${SLAVE_NAME}_slot"

# Настройка standby
cat > "$PGDATA/postgresql.auto.conf" << EOF
primary_conninfo = 'host=$MASTER_HOST port=5432 user=replicator password=replpass application_name=$SLAVE_NAME'
primary_slot_name = '${SLAVE_NAME}_slot'
hot_standby = on
EOF

# Создание файла сигнала standby
touch "$PGDATA/standby.signal"

# Установка правильных разрешений
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"
