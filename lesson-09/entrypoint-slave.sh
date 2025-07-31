#!/bin/bash
set -e

# Функция для логирования
log() {
    echo "[SLAVE-ENTRYPOINT] $1"
}

log "Запуск entrypoint для PostgreSQL слейва"

# Определяем номер слейва из имени хоста
if [[ $POSTGRES_SERVER_NAME == *"slave1"* ]]; then
    SLOT_NAME="replica_slot_1"
elif [[ $POSTGRES_SERVER_NAME == *"slave2"* ]]; then
    SLOT_NAME="replica_slot_2"
else
    log "ОШИБКА: Неизвестное имя сервера: $POSTGRES_SERVER_NAME"
    exit 1
fi

# Проверяем, инициализирован ли слейв
if [ ! -f /var/lib/postgresql/data/standby.signal ]; then
    log "Первый запуск - инициализация слейва $POSTGRES_SERVER_NAME"
    
    # Ожидание готовности мастера
    log "Ожидание готовности мастера..."
    while ! pg_isready -h postgres-master -U postgres -d social_network 2>/dev/null; do 
        log "Мастер еще не готов, ждем..."
        sleep 5
    done
    log "Мастер готов!"
    
    # Очищаем директорию данных
    log "Очистка директории данных"
    rm -rf /var/lib/postgresql/data/*
    
    # Создаем базовую копию с мастера
    log "Создание базовой копии с мастера"
    PGPASSWORD=replicator_password pg_basebackup -h postgres-master -D /var/lib/postgresql/data -U replicator -v -P -W
    
    # Создаем файл конфигурации репликации
    log "Настройка конфигурации репликации"
    cat > /var/lib/postgresql/data/postgresql.auto.conf <<EOF
# Конфигурация репликации
primary_conninfo = 'host=postgres-master port=5432 user=replicator password=replicator_password'
primary_slot_name = '$SLOT_NAME'
EOF
    
    # Создаем standby.signal
    touch /var/lib/postgresql/data/standby.signal
    
    # Устанавливаем правильные права доступа
    chown -R postgres:postgres /var/lib/postgresql/data
    chmod 700 /var/lib/postgresql/data
    
    log "Слейв $POSTGRES_SERVER_NAME настроен с слотом $SLOT_NAME"
else
    log "Слейв уже настроен, пропускаем инициализацию"
fi

# Запускаем PostgreSQL в standby режиме
log "Запуск PostgreSQL в standby режиме"
exec gosu postgres postgres \
    -c hot_standby=on \
    -c wal_receiver_timeout=60s \
    -c wal_receiver_status_interval=10s \
    -c hba_file=/etc/postgresql/pg_hba.conf 