#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директории и файлы
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/websocket_server.pid"
LOG_FILE="$LOG_DIR/websocket_server.log"

echo -e "${BLUE}🚀 Запуск WebSocket сервера в неинтерактивном режиме${NC}"
echo "=================================================="

# Создаем директорию для логов
mkdir -p "$LOG_DIR"

# Проверяем, запущен ли уже сервер
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Сервер уже запущен (PID: $PID)${NC}"
        echo "Для остановки используйте: ./stop_service.sh"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Найден старый PID файл, удаляем...${NC}"
        rm -f "$PID_FILE"
    fi
fi

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен${NC}"
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose не установлен${NC}"
    exit 1
fi

echo -e "${BLUE}🐳 Запуск Docker сервисов...${NC}"

# Останавливаем существующие контейнеры
docker-compose down --remove-orphans > /dev/null 2>&1

# Запускаем необходимые сервисы
docker-compose up -d citus-coordinator citus-worker-1 citus-worker-2 citus-worker-3 redis rabbitmq app

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка запуска Docker сервисов${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker сервисы запущены${NC}"

# Ожидание готовности PostgreSQL
echo -e "${BLUE}⏳ Ожидание готовности PostgreSQL...${NC}"
for i in {1..30}; do
    if docker-compose exec -T citus-coordinator pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL готов${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ PostgreSQL не готов после 30 секунд${NC}"
        exit 1
    fi
    sleep 1
done

# Ожидание готовности Redis
echo -e "${BLUE}⏳ Ожидание готовности Redis...${NC}"
for i in {1..30}; do
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis готов${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Redis не готов после 30 секунд${NC}"
        exit 1
    fi
    sleep 1
done

# Ожидание готовности RabbitMQ
echo -e "${BLUE}⏳ Ожидание готовности RabbitMQ...${NC}"
for i in {1..60}; do
    if docker-compose exec -T rabbitmq rabbitmqctl status > /dev/null 2>&1; then
        echo -e "${GREEN}✅ RabbitMQ готов${NC}"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "${RED}❌ RabbitMQ не готов после 60 секунд${NC}"
        exit 1
    fi
    sleep 1
done

# Ожидание готовности основного приложения
echo -e "${BLUE}⏳ Ожидание готовности основного приложения...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:9000/docs > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Основное приложение готово${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Основное приложение не готово после 30 секунд${NC}"
        exit 1
    fi
    sleep 1
done

# Создаем виртуальное окружение если его нет
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}🐍 Создание виртуального окружения...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Ошибка создания виртуального окружения${NC}"
        exit 1
    fi
fi

# Активируем виртуальное окружение
source "$VENV_DIR/bin/activate"

# Устанавливаем зависимости
if [ -f requirements.txt ]; then
    echo -e "${BLUE}📦 Установка зависимостей...${NC}"
    pip install -r requirements.txt > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Ошибка установки зависимостей${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Все сервисы готовы!${NC}"
echo "=================================================="
echo -e "${BLUE}📊 Информация о сервисах:${NC}"
echo "  • Основное приложение: http://localhost:9000"
echo "  • PostgreSQL (Citus): localhost:5432"
echo "  • Redis: localhost:6379"
echo "  • RabbitMQ: localhost:5672 (admin:admin123)"
echo "  • RabbitMQ Management: http://localhost:15672"
echo ""

# Запускаем WebSocket сервер в фоне
echo -e "${BLUE}🚀 Запуск WebSocket сервера...${NC}"
echo "  • Сервер: http://localhost:8001"
echo "  • Логи: $LOG_FILE"
echo "  • PID файл: $PID_FILE"

# Запускаем сервер в фоне с перенаправлением логов
nohup python websocket_server.py > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Сохраняем PID
echo $SERVER_PID > "$PID_FILE"

# Ждем немного, чтобы убедиться, что сервер запустился
sleep 3

# Проверяем, что процесс еще работает
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✅ WebSocket сервер запущен (PID: $SERVER_PID)${NC}"
    echo ""
    echo -e "${GREEN}🎯 Сервер готов к работе!${NC}"
else
    echo -e "${RED}❌ Ошибка запуска WebSocket сервера${NC}"
    echo "Проверьте логи: cat $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

# Ожидание полной готовности всех сервисов
echo -e "${BLUE}⏳ Ожидание полной готовности всех сервисов...${NC}"
sleep 5

# Автоматический запуск тестового скрипта
echo -e "${BLUE}🧪 Запуск автоматического тестирования...${NC}"
python test_real_users_demo.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Тестирование завершено успешно!${NC}"
    echo -e "${BLUE}📄 HTML-отчет создан в папке lesson-06/test_report.html${NC}"
    echo -e "${BLUE}🌐 Откройте отчет в браузере для просмотра результатов${NC}"
else
    echo -e "${YELLOW}⚠️ Тестирование завершилось с ошибками${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Сервер готов к работе!${NC}"

# Информация о запущенных сервисах
echo -e "\n${GREEN}🎉 Все сервисы запущены и готовы к работе!${NC}"
echo "Доступные сервисы:"
echo "  • PostgreSQL (Citus): localhost:5432"
echo "  • Redis: localhost:6379"
echo "  • RabbitMQ: localhost:5672 (UI: http://localhost:15672)"
echo "  • WebSocket сервер: http://localhost:8001"
echo "  • Основное приложение: http://localhost:9000" 