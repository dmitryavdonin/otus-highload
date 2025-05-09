#!/bin/bash
# Скрипт для автоматического запуска сервиса и тестирования функциональности диалогов

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Путь к корневой директории проекта (предполагаем, что скрипт запускается из директории lesson-05)
PROJECT_ROOT="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

echo -e "${YELLOW}=== Запуск сервиса и тестирование функциональности диалогов ===${NC}"

# Переходим в корневую директорию проекта
cd "$PROJECT_ROOT"
echo -e "${YELLOW}Текущая директория: $(pwd)${NC}"

# Проверяем наличие скриптов
if [ ! -f "start_services.sh" ]; then
    echo -e "${RED}Ошибка: Скрипт start_services.sh не найден в директории проекта.${NC}"
    exit 1
fi

if [ ! -f "stop_services.sh" ]; then
    echo -e "${RED}Ошибка: Скрипт stop_services.sh не найден в директории проекта.${NC}"
    exit 1
fi

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

# Сначала останавливаем все сервисы
echo -e "${YELLOW}Останавливаем все запущенные сервисы...${NC}"
./stop_services.sh

# Запускаем сервисы с параметром --clean
echo -e "${YELLOW}Запуск сервисов с параметром --clean...${NC}"
./start_services.sh --clean

# Проверяем, что сервисы запущены успешно
echo -e "${YELLOW}Проверяем, что сервисы запущены успешно...${NC}"

# Функция для проверки доступности сервиса
check_service() {
    local max_attempts=30
    local attempt=1
    local wait_time=5
    
    echo -e "${YELLOW}Ожидаем запуск сервиса на порту 9000...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        echo -e "${YELLOW}Попытка $attempt из $max_attempts...${NC}"
        
        # Проверяем доступность сервиса
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/docs; then
            echo -e "${GREEN}Сервис успешно запущен!${NC}"
            return 0
        fi
        
        # Увеличиваем счетчик попыток и ждем перед следующей попыткой
        attempt=$((attempt + 1))
        echo -e "${YELLOW}Ожидаем $wait_time секунд перед следующей попыткой...${NC}"
        sleep $wait_time
    done
    
    echo -e "${RED}Сервис не запустился после $max_attempts попыток. Прерываем выполнение.${NC}"
    return 1
}

# Проверяем доступность сервиса
if ! check_service; then
    echo -e "${RED}Не удалось дождаться запуска сервиса. Проверьте логи: docker-compose -f docker-compose.yml logs app${NC}"
    exit 1
fi

# Запускаем тестирование диалогов
echo -e "${YELLOW}Запуск тестирования диалогов...${NC}"
./lesson-05/test_dialogs.py

# Проверяем результат выполнения тестирования
test_result=$?
if [ $test_result -eq 0 ]; then
    echo -e "${GREEN}Тестирование завершено успешно!${NC}"
else
    echo -e "${RED}Тестирование завершено с ошибкой (код: $test_result).${NC}"
fi

# Спрашиваем пользователя, хочет ли он остановить сервисы
read -p "Остановить сервисы? (y/n): " stop_services

if [ "$stop_services" = "y" ] || [ "$stop_services" = "Y" ]; then
    echo -e "${YELLOW}Останавливаем сервисы...${NC}"
    ./stop_services.sh
    echo -e "${GREEN}Сервисы остановлены.${NC}"
else
    echo -e "${YELLOW}Сервисы продолжают работать. Для остановки выполните ./stop_services.sh${NC}"
fi

echo -e "${GREEN}Выполнение завершено.${NC}"
exit $test_result 