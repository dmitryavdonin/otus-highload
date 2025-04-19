#!/bin/bash
set -e

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Тестирование кворумной синхронной репликации PostgreSQL${NC}"
echo "------------------------------------------------------"

# Проверка статуса репликации на мастере
echo -e "${YELLOW}Проверка статуса репликации:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"

# Проверка задержки репликации
echo -e "\n${YELLOW}Проверка задержки репликации:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -c "SELECT application_name, 
       pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS sent_lag,
       pg_wal_lsn_diff(pg_current_wal_lsn(), write_lsn) AS write_lag,
       pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn) AS flush_lag,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag
FROM pg_stat_replication;"

# Создание тестовой таблицы
echo -e "\n${YELLOW}Создание тестовой таблицы:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -c "
CREATE TABLE IF NOT EXISTS sync_test (
    id SERIAL PRIMARY KEY,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"

# Вставка тестовых данных
echo -e "\n${YELLOW}Вставка тестовых данных:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -c "
INSERT INTO sync_test (data) VALUES ('Test data 1'), ('Test data 2'), ('Test data 3');"

# Проверка данных на слейвах
echo -e "\n${YELLOW}Проверка данных на slave1:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -d social_network -c "SELECT * FROM sync_test;"

echo -e "\n${YELLOW}Проверка данных на slave2:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -c "SELECT * FROM sync_test;"

echo -e "\n${YELLOW}Проверка данных на slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-slave3 psql -U postgres -d social_network -c "SELECT * FROM sync_test;"

# Тестирование кворума - остановка одного слейва
echo -e "\n${YELLOW}Тестирование кворума - остановка slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml stop db-slave3
echo -e "${GREEN}Слейв slave3 остановлен${NC}"

# Вставка данных после остановки одного слейва
echo -e "\n${YELLOW}Вставка данных после остановки slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -c "
INSERT INTO sync_test (data) VALUES ('Test after slave3 down');"

# Проверка данных на оставшихся слейвах
echo -e "\n${YELLOW}Проверка данных на slave1 после остановки slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -d social_network -c "SELECT * FROM sync_test;"

echo -e "\n${YELLOW}Проверка данных на slave2 после остановки slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -c "SELECT * FROM sync_test;"

# Запуск остановленного слейва
echo -e "\n${YELLOW}Запуск остановленного slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml start db-slave3
echo -e "${GREEN}Слейв slave3 запущен${NC}"

# Ожидание восстановления репликации
echo -e "\n${YELLOW}Ожидание восстановления репликации (10 секунд)...${NC}"
sleep 10

# Проверка данных на восстановленном слейве
echo -e "\n${YELLOW}Проверка данных на восстановленном slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-slave3 psql -U postgres -d social_network -c "SELECT * FROM sync_test;"

# Проверка статуса репликации после восстановления
echo -e "\n${YELLOW}Проверка статуса репликации после восстановления:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"

echo -e "\n${GREEN}Тестирование кворумной синхронной репликации завершено!${NC}"
