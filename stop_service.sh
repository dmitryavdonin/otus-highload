#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директории и файлы
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/websocket_server.pid"
LOG_DIR="$PROJECT_DIR/logs"

echo -e "${BLUE}🛑 Остановка WebSocket сервера${NC}"
echo "=================================================="

# Останавливаем WebSocket сервер
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⏳ Остановка WebSocket сервера (PID: $PID)...${NC}"
        kill "$PID"
        
        # Ждем завершения процесса
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ WebSocket сервер остановлен${NC}"
                break
            fi
            if [ $i -eq 10 ]; then
                echo -e "${YELLOW}⚠️  Принудительная остановка...${NC}"
                kill -9 "$PID" 2>/dev/null || true
            fi
            sleep 1
        done
    else
        echo -e "${YELLOW}⚠️  Процесс с PID $PID не найден${NC}"
    fi
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}⚠️  PID файл не найден, сервер возможно не запущен${NC}"
fi

# Останавливаем Docker сервисы
echo -e "${BLUE}🐳 Остановка Docker сервисов...${NC}"
docker-compose down --remove-orphans

# Удаление volumes
echo -e "${BLUE}🗑️  Удаление Docker volumes...${NC}"
docker-compose down -v

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker сервисы и volumes удалены${NC}"
else
    echo -e "${YELLOW}⚠️  Ошибка остановки Docker сервисов${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Все сервисы остановлены и данные очищены!${NC}" 