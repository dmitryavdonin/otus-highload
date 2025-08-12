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
docker-compose -f docker-compose-sync-replication.yml ps

# Проверка статуса репликации
echo -e "\n${YELLOW}Проверка статуса репликации:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Создание таблицы users, если она не существует
echo -e "\n${YELLOW}Проверка наличия таблицы users:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -c "\dt users"

# Проверка количества пользователей перед тестом
echo -e "\n${YELLOW}Проверка количества пользователей перед тестом:${NC}"
USERS_BEFORE=$(docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_BEFORE=$(echo $USERS_BEFORE | tr -d ' ')
echo "Количество пользователей перед тестом: $USERS_BEFORE"

# Шаг 1: Запускаем нагрузку на запись (1 миллион пользователей)
echo -e "\n${YELLOW}Запуск нагрузки на запись (1 миллион пользователей):${NC}"
/home/busybox/dev/otus-highload/venv/bin/python /home/busybox/dev/otus-highload/lesson-01/load_test_replication.py localhost 1000000 &
LOAD_PID=$!

# Ждем 10 секунд, чтобы нагрузка началась
echo -e "\n${YELLOW}Ожидание 10 секунд для начала нагрузки...${NC}"
sleep 10

# Шаг 2: Убиваем одну из реплик (db-slave3)
echo -e "\n${YELLOW}Остановка db-slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml stop db-slave3

# Шаг 3: Ждем несколько секунд и останавливаем нагрузку
echo -e "\n${YELLOW}Ожидание 5 секунд...${NC}"
sleep 5
echo -e "\n${YELLOW}Остановка нагрузки:${NC}"
kill -SIGINT $LOAD_PID
wait $LOAD_PID

# Проверка количества пользователей после первой фазы
echo -e "\n${YELLOW}Проверка количества пользователей после первой фазы:${NC}"
USERS_AFTER_PHASE1=$(docker-compose -f docker-compose-sync-replication.yml exec db-master psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_AFTER_PHASE1=$(echo $USERS_AFTER_PHASE1 | tr -d ' ')
echo "Количество пользователей после первой фазы: $USERS_AFTER_PHASE1"
echo "Добавлено пользователей: $((USERS_AFTER_PHASE1 - USERS_BEFORE))"

# Проверка количества пользователей на слейвах
echo -e "\n${YELLOW}Проверка количества пользователей на db-slave1:${NC}"
USERS_SLAVE1=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave1 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_SLAVE1=$(echo $USERS_SLAVE1 | tr -d ' ')
echo "Количество пользователей на db-slave1: $USERS_SLAVE1"

echo -e "\n${YELLOW}Проверка количества пользователей на db-slave2:${NC}"
USERS_SLAVE2=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_SLAVE2=$(echo $USERS_SLAVE2 | tr -d ' ')
echo "Количество пользователей на db-slave2: $USERS_SLAVE2"

# Шаг 4: Промоутим db-slave2 до мастера
echo -e "\n${YELLOW}Промоутим db-slave2 до мастера:${NC}"
docker-compose -f docker-compose-sync-replication.yml exec -u postgres db-slave2 pg_ctl promote -D /var/lib/postgresql/data

# Ожидание завершения промоута
echo -e "\n${YELLOW}Ожидание завершения промоута (5 секунд)...${NC}"
sleep 5

# Проверка, что db-slave2 стал мастером
echo -e "\n${YELLOW}Проверка, что db-slave2 стал мастером:${NC}"
IS_MASTER=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -t -c "SELECT pg_is_in_recovery();")
IS_MASTER=$(echo $IS_MASTER | tr -d ' ')
if [ "$IS_MASTER" == "f" ]; then
    echo -e "${GREEN}db-slave2 успешно стал мастером!${NC}"
else
    echo -e "${RED}db-slave2 не стал мастером!${NC}"
    exit 1
fi

# Шаг 5: Возобновляем нагрузку на запись на новый мастер
echo -e "\n${YELLOW}Возобновление нагрузки на запись (500000 пользователей) на новый мастер:${NC}"
/home/busybox/dev/otus-highload/venv/bin/python /home/busybox/dev/otus-highload/lesson-01/load_test_replication.py localhost:5434 500000 &
LOAD_PID=$!

# Ждем завершения нагрузки
wait $LOAD_PID

# Шаг 6: Проверяем, есть ли потери транзакций
echo -e "\n${YELLOW}Проверка количества пользователей после второй фазы:${NC}"
USERS_AFTER_PHASE2=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave2 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_AFTER_PHASE2=$(echo $USERS_AFTER_PHASE2 | tr -d ' ')
echo "Количество пользователей после второй фазы: $USERS_AFTER_PHASE2"
echo "Добавлено пользователей во второй фазе: $((USERS_AFTER_PHASE2 - USERS_AFTER_PHASE1))"
echo "Всего добавлено пользователей: $((USERS_AFTER_PHASE2 - USERS_BEFORE))"

# Запускаем db-slave3 снова
echo -e "\n${YELLOW}Запуск db-slave3:${NC}"
docker-compose -f docker-compose-sync-replication.yml start db-slave3

# Ожидание восстановления db-slave3
echo -e "\n${YELLOW}Ожидание восстановления db-slave3 (20 секунд)...${NC}"
sleep 20

# Проверка данных на db-slave3
echo -e "\n${YELLOW}Проверка количества пользователей на db-slave3:${NC}"
USERS_SLAVE3=$(docker-compose -f docker-compose-sync-replication.yml exec db-slave3 psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM users;")
USERS_SLAVE3=$(echo $USERS_SLAVE3 | tr -d ' ')
echo "Количество пользователей на db-slave3: $USERS_SLAVE3"

# Шаг 7: Выводим результаты
echo -e "\n${YELLOW}Результаты эксперимента:${NC}"
echo "------------------------------------------------------"
echo "Количество пользователей перед тестом: $USERS_BEFORE"
echo "Количество пользователей после первой фазы: $USERS_AFTER_PHASE1"
echo "Количество пользователей после второй фазы: $USERS_AFTER_PHASE2"
echo "Количество пользователей на db-slave1: $USERS_SLAVE1"
echo "Количество пользователей на db-slave3 после восстановления: $USERS_SLAVE3"

# Проверка на потерю данных
if [ "$USERS_AFTER_PHASE1" -eq "$USERS_SLAVE1" ]; then
    echo -e "\n${GREEN}Потери данных не обнаружены в первой фазе! Мастер и db-slave1 имеют одинаковое количество пользователей.${NC}"
else
    echo -e "\n${RED}Обнаружены потери данных в первой фазе! Разница между мастером и db-slave1: $((USERS_AFTER_PHASE1 - USERS_SLAVE1)) пользователей.${NC}"
fi

if [ "$USERS_AFTER_PHASE2" -eq "$USERS_SLAVE3" ]; then
    echo -e "\n${GREEN}Потери данных не обнаружены во второй фазе! Новый мастер и db-slave3 имеют одинаковое количество пользователей.${NC}"
else
    echo -e "\n${RED}Обнаружены потери данных во второй фазе! Разница между новым мастером и db-slave3: $((USERS_AFTER_PHASE2 - USERS_SLAVE3)) пользователей.${NC}"
fi

echo -e "\n${GREEN}Тестирование кворумной репликации PostgreSQL завершено!${NC}"
