#!/bin/bash
# Скрипт для автоматического тестирования функциональности диалогов после выполнения setup.sh

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Путь к корневой директории проекта (предполагаем, что скрипт запускается из директории lesson-05)
PROJECT_ROOT="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

echo -e "${YELLOW}=== Тестирование функциональности диалогов в социальной сети с Citus ===${NC}"

# Переходим в корневую директорию проекта
cd "$PROJECT_ROOT"
echo -e "${YELLOW}Текущая директория: $(pwd)${NC}"

# Проверяем наличие скрипта тестирования диалогов
if [ ! -f "lesson-05/test_dialogs.py" ]; then
    echo -e "${RED}Ошибка: Скрипт test_dialogs.py не найден в директории lesson-05.${NC}"
    exit 1
fi

# Проверяем, что скрипт тестирования диалогов имеет права на исполнение
if [ ! -x "lesson-05/test_dialogs.py" ]; then
    echo -e "${YELLOW}Выдаем права на исполнение для скрипта test_dialogs.py...${NC}"
    chmod +x "lesson-05/test_dialogs.py"
fi

# Проверяем, что Docker работает
echo -e "${YELLOW}Проверяем, что Docker работает...${NC}"
if ! docker ps &>/dev/null; then
    echo -e "${RED}Docker не запущен или у вас нет прав для его использования.${NC}"
    exit 1
fi

# Проверяем текущий статус контейнеров
echo -e "${YELLOW}Проверяем текущий статус контейнеров...${NC}"
docker ps

# Функция для проверки доступности сервиса
check_service() {
    local max_attempts=30
    local attempt=1
    local wait_time=5
    
    echo -e "${YELLOW}Проверяем доступность сервиса на порту 9000...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        echo -e "${YELLOW}Попытка $attempt из $max_attempts...${NC}"
        
        # Проверяем доступность сервиса
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/docs | grep -q "200"; then
            echo -e "${GREEN}Сервис успешно запущен!${NC}"
            return 0
        fi
        
        # Увеличиваем счетчик попыток и ждем перед следующей попыткой
        attempt=$((attempt + 1))
        echo -e "${YELLOW}Ожидаем $wait_time секунд перед следующей попыткой...${NC}"
        sleep $wait_time
    done
    
    echo -e "${RED}Сервис не запустился после $max_attempts попыток.${NC}"
    return 1
}

# Проверяем, запущен ли какой-либо из контейнеров нашего приложения
if ! docker ps | grep -q -e "otus-highload-app" -e "citus-coordinator"; then
    echo -e "${YELLOW}Контейнеры приложения не запущены. Запускаем скрипт настройки...${NC}"
    
    # Запуск скрипта настройки
    echo -e "${YELLOW}Запуск скрипта настройки...${NC}"
    ./lesson-05/setup.sh
    
    # Ждем некоторое время, чтобы контейнеры успели запуститься
    echo -e "${YELLOW}Ожидаем 60 секунд, чтобы контейнеры успели запуститься...${NC}"
    sleep 60
    
    # Проверяем текущий статус контейнеров
    echo -e "${YELLOW}Текущий статус контейнеров:${NC}"
    docker ps
    
    # Проверяем доступность сервиса
    if ! check_service; then
        echo -e "${RED}Не удалось запустить сервис. Проверьте логи:${NC}"
        docker-compose logs app
        exit 1
    fi
else
    echo -e "${GREEN}Контейнеры приложения уже запущены.${NC}"
    
    # Проверяем доступность сервиса
    if ! check_service; then
        echo -e "${RED}Сервис запущен, но недоступен. Перезапускаем контейнеры...${NC}"
        docker-compose restart app
        
        # Ждем перезапуска
        echo -e "${YELLOW}Ожидаем 30 секунд для перезапуска сервиса...${NC}"
        sleep 30
        
        # Проверяем доступность после перезапуска
        if ! check_service; then
            echo -e "${RED}Не удалось запустить сервис даже после перезапуска. Проверьте логи:${NC}"
            docker-compose logs app
            exit 1
        fi
    fi
fi

# Запускаем тестирование диалогов в автоматическом режиме
echo -e "${YELLOW}Запуск тестирования диалогов в автоматическом режиме...${NC}"
./lesson-05/test_dialogs.py --auto --wait-service 60 --message-count 5 --skip-citus-check

# Проверяем результат выполнения тестирования
test_result=$?
if [ $test_result -eq 0 ]; then
    echo -e "${GREEN}Тестирование завершено успешно!${NC}"
else
    echo -e "${RED}Тестирование завершено с ошибкой (код: $test_result).${NC}"
fi

# Предлагаем пользователю посмотреть логи приложения
read -p "Хотите просмотреть логи приложения? (y/n): " view_logs
if [ "$view_logs" = "y" ] || [ "$view_logs" = "Y" ]; then
    echo -e "${YELLOW}Последние 50 строк логов приложения:${NC}"
    # Используем более гибкий подход к поиску контейнера приложения
    app_container=$(docker ps | grep -oE "(otus-highload-app-1|otus-highload-app)" | head -n 1)
    if [ -n "$app_container" ]; then
        docker logs "$app_container" | tail -n 50
    else
        echo -e "${RED}Контейнер приложения не найден.${NC}"
    fi
fi

# Предлагаем пользователю посмотреть логи координатора Citus
read -p "Хотите просмотреть логи координатора Citus? (y/n): " view_citus_logs
if [ "$view_citus_logs" = "y" ] || [ "$view_citus_logs" = "Y" ]; then
    echo -e "${YELLOW}Последние 50 строк логов координатора Citus:${NC}"
    docker logs citus-coordinator | tail -n 50
fi

# Предлагаем выполнить запрос к БД для проверки содержимого таблицы dialog_messages
read -p "Хотите проверить содержимое таблицы dialog_messages в БД? (y/n): " check_db
if [ "$check_db" = "y" ] || [ "$check_db" = "Y" ]; then
    echo -e "${YELLOW}Запрос к БД для проверки таблицы dialog_messages:${NC}"
    docker exec citus-coordinator psql -U postgres -d social_network -c "SELECT count(*) FROM dialog_messages;"
    docker exec citus-coordinator psql -U postgres -d social_network -c "SELECT * FROM dialog_messages LIMIT 5;"
fi

echo -e "${GREEN}Выполнение завершено.${NC}"
exit $test_result 