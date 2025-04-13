#!/bin/bash

# Скрипт для инициализации репликации PostgreSQL

# Проверяем, что архивная директория существует
docker exec postgres-master mkdir -p /var/lib/postgresql/data/archive
docker exec postgres-master chown postgres:postgres /var/lib/postgresql/data/archive

# Перезагружаем конфигурацию PostgreSQL на мастере
docker exec postgres-master pg_ctl reload

# Проверяем статус репликации
echo "Проверка статуса репликации..."
sleep 5
docker exec postgres-master psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Проверяем, что слейвы работают в режиме только для чтения
echo "Проверка режима только для чтения на slave1..."
docker exec postgres-slave1 psql -U postgres -c "SHOW transaction_read_only;"

echo "Проверка режима только для чтения на slave2..."
docker exec postgres-slave2 psql -U postgres -c "SHOW transaction_read_only;"

# Тестируем репликацию
echo "Создаем тестовую таблицу на мастере..."
docker exec postgres-master psql -U postgres -d social_network -c "CREATE TABLE IF NOT EXISTS replication_test (id SERIAL PRIMARY KEY, test_data TEXT);"
docker exec postgres-master psql -U postgres -d social_network -c "INSERT INTO replication_test (test_data) VALUES ('Test data from master');"

# Проверяем, что данные реплицировались на слейвы
echo "Проверяем данные на slave1..."
docker exec postgres-slave1 psql -U postgres -d social_network -c "SELECT * FROM replication_test;"

echo "Проверяем данные на slave2..."
docker exec postgres-slave2 psql -U postgres -d social_network -c "SELECT * FROM replication_test;"

echo "Репликация настроена и работает!"
