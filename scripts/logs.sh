#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директории и файлы
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/websocket_server.log"
PID_FILE="$PROJECT_DIR/websocket_server.pid"

# Функция помощи
show_help() {
    echo -e "${BLUE}📋 Просмотр логов WebSocket сервера${NC}"
    echo "=================================================="
    echo "Использование: $0 [ОПЦИЯ]"
    echo ""
    echo "Опции:"
    echo "  -f, --follow     Следить за логами в реальном времени (tail -f)"
    echo "  -l, --last N     Показать последние N строк (по умолчанию 50)"
    echo "  -c, --clear      Очистить логи"
    echo "  -s, --status     Показать статус сервера"
    echo "  -h, --help       Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0               Показать последние 50 строк логов"
    echo "  $0 -f            Следить за логами в реальном времени"
    echo "  $0 -l 100        Показать последние 100 строк"
    echo "  $0 -s            Показать статус сервера"
}

# Функция проверки статуса сервера
show_status() {
    echo -e "${BLUE}📊 Статус WebSocket сервера${NC}"
    echo "=================================================="
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Сервер запущен (PID: $PID)${NC}"
            
            # Показываем информацию о процессе
            echo -e "${BLUE}📈 Информация о процессе:${NC}"
            ps -p "$PID" -o pid,ppid,cmd,etime,pcpu,pmem --no-headers | while read line; do
                echo "  $line"
            done
            
            # Проверяем доступность сервера
            echo -e "${BLUE}🌐 Проверка доступности:${NC}"
            if curl -s http://localhost:8001/health > /dev/null 2>&1; then
                echo -e "  ${GREEN}✅ HTTP сервер доступен${NC}"
            else
                echo -e "  ${RED}❌ HTTP сервер недоступен${NC}"
            fi
            
        else
            echo -e "${RED}❌ Сервер не запущен (PID файл найден, но процесс не существует)${NC}"
            echo -e "${YELLOW}💡 Удалите PID файл: rm $PID_FILE${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Сервер не запущен (PID файл не найден)${NC}"
    fi
    
    # Проверяем наличие логов
    if [ -f "$LOG_FILE" ]; then
        LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
        LOG_LINES=$(wc -l < "$LOG_FILE")
        echo -e "${BLUE}📄 Лог файл:${NC}"
        echo "  Путь: $LOG_FILE"
        echo "  Размер: $LOG_SIZE"
        echo "  Строк: $LOG_LINES"
    else
        echo -e "${YELLOW}⚠️  Лог файл не найден: $LOG_FILE${NC}"
    fi
}

# Функция очистки логов
clear_logs() {
    echo -e "${YELLOW}🗑️  Очистка логов...${NC}"
    if [ -f "$LOG_FILE" ]; then
        > "$LOG_FILE"
        echo -e "${GREEN}✅ Логи очищены${NC}"
    else
        echo -e "${YELLOW}⚠️  Лог файл не найден${NC}"
    fi
}

# Функция показа логов
show_logs() {
    local lines=${1:-50}
    
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}❌ Лог файл не найден: $LOG_FILE${NC}"
        echo -e "${YELLOW}💡 Возможно сервер еще не запускался${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📄 Последние $lines строк логов:${NC}"
    echo "=================================================="
    tail -n "$lines" "$LOG_FILE"
}

# Функция следования за логами
follow_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}❌ Лог файл не найден: $LOG_FILE${NC}"
        echo -e "${YELLOW}💡 Возможно сервер еще не запускался${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📄 Следование за логами (Ctrl+C для выхода):${NC}"
    echo "=================================================="
    tail -f "$LOG_FILE"
}

# Обработка аргументов командной строки
case "${1:-}" in
    -f|--follow)
        follow_logs
        ;;
    -l|--last)
        if [ -n "$2" ] && [ "$2" -eq "$2" ] 2>/dev/null; then
            show_logs "$2"
        else
            echo -e "${RED}❌ Неверное количество строк: $2${NC}"
            show_help
            exit 1
        fi
        ;;
    -c|--clear)
        clear_logs
        ;;
    -s|--status)
        show_status
        ;;
    -h|--help)
        show_help
        ;;
    "")
        show_logs
        ;;
    *)
        echo -e "${RED}❌ Неизвестная опция: $1${NC}"
        show_help
        exit 1
        ;;
esac 