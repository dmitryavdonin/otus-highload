#!/bin/bash
set -e

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Тестирование кворумной репликации PostgreSQL${NC}"
echo "------------------------------------------------------"

# Проверка статуса кластера
echo -e "${YELLOW}Проверка статуса кластера:${NC}"
docker-compose -f docker-compose-pg-replication.yml ps

# Проверка статуса репликации
echo -e "\n${YELLOW}Проверка статуса репликации:${NC}"
docker-compose -f docker-compose-pg-replication.yml exec db-master psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Создание таблицы test_replication, если она не существует
echo -e "\n${YELLOW}Создание таблицы test_replication:${NC}"
docker-compose -f docker-compose-pg-replication.yml exec db-master psql -U postgres -d social_network -c "
CREATE TABLE IF NOT EXISTS test_replication (
    id SERIAL PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"

# Проверка количества записей перед тестом
echo -e "\n${YELLOW}Проверка количества записей перед тестом:${NC}"
RECORDS_BEFORE=$(docker-compose -f docker-compose-pg-replication.yml exec db-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_BEFORE=$(echo $RECORDS_BEFORE | tr -d ' ')
echo "Количество записей перед тестом: $RECORDS_BEFORE"

# Шаг 1: Добавляем 1000 записей в таблицу
echo -e "\n${YELLOW}Добавление 1000 записей в таблицу:${NC}"
for i in {1..1000}; do
    docker-compose -f docker-compose-pg-replication.yml exec -T db-master psql -U postgres -d social_network -c "INSERT INTO test_replication (data) VALUES ('Test data $i');"
    if [ $((i % 100)) -eq 0 ]; then
        echo "Добавлено $i записей..."
    fi
done

# Проверка количества записей после первой фазы
echo -e "\n${YELLOW}Проверка количества записей после первой фазы:${NC}"
RECORDS_AFTER_PHASE1=$(docker-compose -f docker-compose-pg-replication.yml exec db-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_AFTER_PHASE1=$(echo $RECORDS_AFTER_PHASE1 | tr -d ' ')
echo "Количество записей после первой фазы: $RECORDS_AFTER_PHASE1"
echo "Добавлено записей: $((RECORDS_AFTER_PHASE1 - RECORDS_BEFORE))"

# Проверка количества записей на слейвах
echo -e "\n${YELLOW}Проверка количества записей на db-slave1:${NC}"
RECORDS_SLAVE1=$(docker-compose -f docker-compose-pg-replication.yml exec db-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_SLAVE1=$(echo $RECORDS_SLAVE1 | tr -d ' ')
echo "Количество записей на db-slave1: $RECORDS_SLAVE1"

echo -e "\n${YELLOW}Проверка количества записей на db-slave2:${NC}"
RECORDS_SLAVE2=$(docker-compose -f docker-compose-pg-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_SLAVE2=$(echo $RECORDS_SLAVE2 | tr -d ' ')
echo "Количество записей на db-slave2: $RECORDS_SLAVE2"

# Шаг 2: Убиваем одну из реплик (db-slave2)
echo -e "\n${YELLOW}Остановка db-slave2:${NC}"
docker-compose -f docker-compose-pg-replication.yml stop db-slave2

# Шаг 3: Добавляем еще 500 записей в таблицу
echo -e "\n${YELLOW}Добавление еще 500 записей в таблицу:${NC}"
for i in {1..500}; do
    docker-compose -f docker-compose-pg-replication.yml exec -T db-master psql -U postgres -d social_network -c "INSERT INTO test_replication (data) VALUES ('Test data after slave2 stop $i');"
    if [ $((i % 100)) -eq 0 ]; then
        echo "Добавлено $i записей..."
    fi
done

# Проверка количества записей после второй фазы
echo -e "\n${YELLOW}Проверка количества записей после второй фазы:${NC}"
RECORDS_AFTER_PHASE2=$(docker-compose -f docker-compose-pg-replication.yml exec db-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_AFTER_PHASE2=$(echo $RECORDS_AFTER_PHASE2 | tr -d ' ')
echo "Количество записей после второй фазы: $RECORDS_AFTER_PHASE2"
echo "Добавлено записей во второй фазе: $((RECORDS_AFTER_PHASE2 - RECORDS_AFTER_PHASE1))"
echo "Всего добавлено записей: $((RECORDS_AFTER_PHASE2 - RECORDS_BEFORE))"

# Проверка количества записей на db-slave1
echo -e "\n${YELLOW}Проверка количества записей на db-slave1 после второй фазы:${NC}"
RECORDS_SLAVE1_PHASE2=$(docker-compose -f docker-compose-pg-replication.yml exec db-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_SLAVE1_PHASE2=$(echo $RECORDS_SLAVE1_PHASE2 | tr -d ' ')
echo "Количество записей на db-slave1: $RECORDS_SLAVE1_PHASE2"

# Шаг 4: Запускаем db-slave2 снова
echo -e "\n${YELLOW}Запуск db-slave2:${NC}"
docker-compose -f docker-compose-pg-replication.yml start db-slave2

# Ожидание восстановления db-slave2
echo -e "\n${YELLOW}Ожидание восстановления db-slave2 (10 секунд)...${NC}"
sleep 10

# Проверка данных на db-slave2
echo -e "\n${YELLOW}Проверка количества записей на db-slave2:${NC}"
RECORDS_SLAVE2_AFTER=$(docker-compose -f docker-compose-pg-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM test_replication;")
RECORDS_SLAVE2_AFTER=$(echo $RECORDS_SLAVE2_AFTER | tr -d ' ')
echo "Количество записей на db-slave2: $RECORDS_SLAVE2_AFTER"

# Шаг 5: Выводим результаты
echo -e "\n${YELLOW}Результаты эксперимента:${NC}"
echo "------------------------------------------------------"
echo "Количество записей перед тестом: $RECORDS_BEFORE"
echo "Количество записей после первой фазы: $RECORDS_AFTER_PHASE1"
echo "Количество записей после второй фазы: $RECORDS_AFTER_PHASE2"
echo "Количество записей на db-slave1 после первой фазы: $RECORDS_SLAVE1"
echo "Количество записей на db-slave1 после второй фазы: $RECORDS_SLAVE1_PHASE2"
echo "Количество записей на db-slave2 после первой фазы: $RECORDS_SLAVE2"
echo "Количество записей на db-slave2 после восстановления: $RECORDS_SLAVE2_AFTER"

# Проверка на потерю данных
if [ "$RECORDS_AFTER_PHASE1" -eq "$RECORDS_SLAVE1" ]; then
    echo -e "\n${GREEN}Потери данных не обнаружены в первой фазе! Мастер и db-slave1 имеют одинаковое количество записей.${NC}"
else
    echo -e "\n${RED}Обнаружены потери данных в первой фазе! Разница между мастером и db-slave1: $((RECORDS_AFTER_PHASE1 - RECORDS_SLAVE1)) записей.${NC}"
fi

if [ "$RECORDS_AFTER_PHASE2" -eq "$RECORDS_SLAVE1_PHASE2" ]; then
    echo -e "\n${GREEN}Потери данных не обнаружены во второй фазе! Мастер и db-slave1 имеют одинаковое количество записей.${NC}"
else
    echo -e "\n${RED}Обнаружены потери данных во второй фазе! Разница между мастером и db-slave1: $((RECORDS_AFTER_PHASE2 - RECORDS_SLAVE1_PHASE2)) записей.${NC}"
fi

if [ "$RECORDS_AFTER_PHASE2" -eq "$RECORDS_SLAVE2_AFTER" ]; then
    echo -e "\n${GREEN}Потери данных не обнаружены после восстановления db-slave2! Мастер и db-slave2 имеют одинаковое количество записей.${NC}"
else
    echo -e "\n${RED}Обнаружены потери данных после восстановления db-slave2! Разница между мастером и db-slave2: $((RECORDS_AFTER_PHASE2 - RECORDS_SLAVE2_AFTER)) записей.${NC}"
fi

echo -e "\n${GREEN}Тестирование кворумной репликации PostgreSQL завершено!${NC}"
