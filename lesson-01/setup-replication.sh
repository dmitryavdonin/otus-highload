#!/bin/bash

# Скрипт для настройки репликации PostgreSQL

# Создаем pg_hba.conf с правильными настройками
cat > pg_hba.conf << EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD
# Allow replication connections from all hosts
host    replication     postgres        0.0.0.0/0               md5
host    replication     postgres        172.20.0.0/16           trust
# Allow regular connections from all hosts
host    all             postgres        0.0.0.0/0               md5
host    all             postgres        172.20.0.0/16           md5
EOF

# Копируем pg_hba.conf в контейнер мастера
docker cp pg_hba.conf postgres-master:/var/lib/postgresql/data/pg_hba.conf

# Устанавливаем правильные права на файл
docker exec postgres-master chmod 600 /var/lib/postgresql/data/pg_hba.conf
docker exec postgres-master chown postgres:postgres /var/lib/postgresql/data/pg_hba.conf

# Перезагружаем конфигурацию PostgreSQL на мастере
docker exec postgres-master pg_ctl reload

# Создаем директорию для архивов WAL
docker exec postgres-master mkdir -p /var/lib/postgresql/data/archive
docker exec postgres-master chown postgres:postgres /var/lib/postgresql/data/archive

echo "Настройка репликации завершена. Проверьте статус репликации через несколько секунд."
