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

# Параметры по умолчанию
BACKEND="postgresql"

# Обработка аргументов командной строки
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            BACKEND="$2"
            shift 2
            ;;
        --help|-h)
            echo "Использование: $0 [--backend postgresql|redis]"
            echo ""
            echo "Опции:"
            echo "  --backend    Выбор бэкенда для диалогов (postgresql или redis)"
            echo "  --help       Показать эту справку"
            echo ""
            echo "Примеры:"
            echo "  $0                           # Запуск с PostgreSQL"
            echo "  $0 --backend postgresql     # Запуск с PostgreSQL"
            echo "  $0 --backend redis          # Запуск с Redis"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Неизвестный параметр: $1${NC}"
            echo "Используйте --help для справки"
            exit 1
            ;;
    esac
done

# Проверка корректности бэкенда
if [[ "$BACKEND" != "postgresql" && "$BACKEND" != "redis" ]]; then
    echo -e "${RED}❌ Неверный бэкенд: $BACKEND${NC}"
    echo "Доступные бэкенды: postgresql, redis"
    exit 1
fi

echo -e "${BLUE}🚀 Запуск сервисов с бэкендом: $BACKEND${NC}"
echo "=================================================="

# Создаем директорию для логов
mkdir -p "$LOG_DIR"

# Проверяем, запущен ли уже сервер
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  WebSocket сервер уже запущен (PID: $PID)${NC}"
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

echo -e "${BLUE}🐳 Запуск Docker сервисов с бэкендом: $BACKEND${NC}"

# Останавливаем существующие контейнеры
echo -e "${BLUE}🛑 Остановка существующих контейнеров...${NC}"
docker-compose down --remove-orphans > /dev/null 2>&1

# Пересобираем образ приложения
echo -e "${BLUE}🔨 Пересборка образа приложения...${NC}"
docker-compose build app
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка пересборки образа приложения${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Образ приложения пересобран${NC}"

# Устанавливаем переменную окружения для бэкенда
export DIALOG_BACKEND=$BACKEND

# Запускаем сервисы
docker-compose up -d

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка запуска Docker сервисов${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker сервисы запущены с бэкендом: $BACKEND${NC}"

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

# Определяем имя контейнера приложения
APP_CONTAINER="app"

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
echo "  • Бэкенд диалогов: $BACKEND"
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

echo ""
echo -e "${GREEN}🎉 Все сервисы запущены и готовы к работе!${NC}"
echo "=================================================="
echo -e "${BLUE}📊 Доступные сервисы:${NC}"
echo "  • Основное приложение: http://localhost:9000"
echo "  • PostgreSQL (Citus): localhost:5432"
echo "  • Redis: localhost:6379"
echo "  • RabbitMQ: localhost:5672 (UI: http://localhost:15672)"
echo "  • WebSocket сервер: http://localhost:8001"
echo "  • Бэкенд диалогов: $BACKEND"
echo ""
echo -e "${YELLOW}💡 Для тестирования производительности диалогов:${NC}"
if [ "$BACKEND" = "redis" ]; then
    echo "   ./run_dialog_performance_test_redis.sh"
else
    echo "   ./run_dialog_performance_test.sh"
fi
echo ""
echo -e "${YELLOW}💡 Для остановки всех сервисов используйте:${NC}"
echo "   ./stop_service.sh" 