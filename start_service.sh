#!/bin/bash

# ==============================================================================
# Скрипт для запуска Dialog Service и его зависимостей (ДЗ-8)
# ==============================================================================

# -- Настройки и переменные --
# Цвета для красивого вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Параметры по умолчанию
BACKEND="redis"
COMPOSE_FILE="docker-compose.yml"

# -- Функции --
function print_help {
    echo "Использование: $0 [--backend postgresql|redis]"
    echo ""
    echo "Опции:"
    echo "  --backend    Выбор бэкенда для Dialog Service (postgresql или redis). По умолчанию: redis."
    echo "  --help, -h   Показать эту справку."
    echo ""
    echo "Примеры:"
    echo "  $0                           # Запуск с Redis (с использованием UDF)"
    echo "  $0 --backend postgresql     # Запуск с PostgreSQL"
}

# -- Обработка аргументов --
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            BACKEND="$2"
            shift 2
            ;;
        --help|-h)
            print_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Неизвестный параметр: $1${NC}"
            print_help
            exit 1
            ;;
    esac
done

# Проверка корректности бэкенда
if [[ "$BACKEND" != "postgresql" && "$BACKEND" != "redis" ]]; then
    echo -e "${RED}❌ Неверный бэкенд: '$BACKEND'. Доступные: postgresql, redis.${NC}"
    exit 1
fi

# -- Основная логика --
echo -e "${BLUE}🚀 Запуск системы для Dialog Service с бэкендом: $BACKEND${NC}"
echo "=================================================="

# Проверка наличия Docker и Docker Compose
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker или Docker Compose не установлены. Пожалуйста, установите их.${NC}"
    exit 1
fi

# 1. Устанавливаем переменную окружения для docker-compose
export DIALOG_BACKEND=$BACKEND
echo -e "[INFO] Установлена переменная окружения: DIALOG_BACKEND=${GREEN}$BACKEND${NC}"

# 2. Останавливаем существующие контейнеры, чтобы избежать конфликтов
echo -e "${BLUE}🛑 Остановка существующих сервисов...${NC}"
docker-compose -f $COMPOSE_FILE down --remove-orphans > /dev/null 2>&1

# 3. Сборка образов
echo -e "${BLUE}🔨 Сборка Docker-образов (monolith, dialog-service)...${NC}"
docker-compose -f $COMPOSE_FILE build
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка сборки Docker-образов.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Образы успешно собраны.${NC}"

# 4. Запуск всех сервисов в фоновом режиме
echo -e "${BLUE}🐳 Запуск сервисов через docker-compose...${NC}"
docker-compose -f $COMPOSE_FILE up -d
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка запуска сервисов через docker-compose.${NC}"
    exit 1
fi

# 5. Ожидание готовности Dialog Service
DIALOG_SERVICE_URL="http://localhost:8002/health"
echo -e "${BLUE}⏳ Ожидание готовности Dialog Service по адресу: $DIALOG_SERVICE_URL...${NC}"

for i in {1..45}; do
    # Проверяем health-check с помощью curl
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" $DIALOG_SERVICE_URL)
    if [ "$STATUS_CODE" -eq 200 ]; then
        echo -e "${GREEN}✅ Dialog Service готов и отвечает на порту 8002!${NC}"
        break
    fi
    
    # Проверка, не упал ли контейнер
    CONTAINER_STATUS=$(docker-compose -f $COMPOSE_FILE ps dialog-service | grep "dialog-service")
    if [[ $CONTAINER_STATUS != *"Up"* && $CONTAINER_STATUS != *"healthy"* ]]; then
        echo -e "${RED}❌ Контейнер 'dialog-service' не запустился или упал.${NC}"
        echo -e "${YELLOW}   Проверьте логи: docker-compose logs dialog-service${NC}"
        exit 1
    fi

    if [ $i -eq 45 ]; then
        echo -e "${RED}❌ Dialog Service не ответил в течение 45 секунд.${NC}"
        echo -e "${YELLOW}   Проверьте логи контейнера: docker-compose logs dialog-service${NC}"
        exit 1
    fi
    sleep 1
done


echo ""
echo "=================================================="
echo -e "${GREEN}🎉 Все сервисы успешно запущены!${NC}"
echo "--------------------------------------------------"
echo -e "${BLUE}  Nginx (прокси):      ${GREEN}http://localhost:80${NC}"
echo -e "${BLUE}  Monolith API:        ${GREEN}http://localhost:8000${NC}"
echo -e "${BLUE}  Dialog Service API:  ${GREEN}http://localhost:8002${NC}"
echo -e "${BLUE}  Бэкенд для диалогов: ${YELLOW}$BACKEND${NC}"
echo "=================================================="
echo ""
echo -e "${YELLOW}💡 Теперь можно запустить тесты:${NC}"
echo "   ./test_dialog_service.sh"
echo ""
echo -e "${YELLOW}💡 Для остановки всех сервисов используйте:${NC}"
echo "   ./stop_service.sh" 