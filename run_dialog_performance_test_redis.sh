#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Запуск тестирования производительности диалогов с Redis UDF${NC}"
echo "=================================================================="

# Проверяем доступность сервиса
echo -e "${BLUE}🔍 Проверка доступности сервиса...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:9000/docs > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Сервис доступен${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Сервис недоступен после 30 попыток${NC}"
        echo -e "${YELLOW}💡 Запустите сервис командой: ./start_service.sh redis${NC}"
        exit 1
    fi
    echo -e "${YELLOW}⏳ Попытка $i/30...${NC}"
    sleep 2
done

# Проверяем наличие виртуального окружения
VENV_DIR="./venv"
if [ -d "$VENV_DIR" ]; then
    echo -e "${BLUE}🐍 Активация виртуального окружения...${NC}"
    source "$VENV_DIR/bin/activate"
    
    # Проверяем наличие aiohttp
    if ! python -c "import aiohttp" 2>/dev/null; then
        echo -e "${BLUE}📦 Установка aiohttp...${NC}"
        pip install aiohttp
    fi
else
    echo -e "${YELLOW}⚠️  Виртуальное окружение не найдено${NC}"
    echo -e "${BLUE}💡 Рекомендуется создать виртуальное окружение:${NC}"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install aiohttp"
    echo ""
    
    # Проверяем системный Python
    if ! python3 -c "import aiohttp" 2>/dev/null; then
        echo -e "${RED}❌ aiohttp не установлен в системном Python${NC}"
        echo "Установите: pip3 install aiohttp"
        exit 1
    fi
fi

# Создаем папку для результатов
mkdir -p lesson-07

# Параметры тестирования
USERS=40
MESSAGES_PER_DIALOG=20
DIALOGS_PER_USER=10

echo -e "${GREEN}✅ Используется Redis UDF бэкенд${NC}"
echo -e "${BLUE}📊 Параметры тестирования:${NC}"
echo "  👥 Пользователи: $USERS"
echo "  💬 Сообщений в диалоге: $MESSAGES_PER_DIALOG"
echo "  📝 Диалогов на пользователя: $DIALOGS_PER_USER"
echo "  🔧 Результаты: lesson-07/dialog_metrics_redis_udf.json"
echo ""

# Устанавливаем переменную окружения для Redis UDF
export DIALOG_BACKEND=redis

# Запускаем тест
echo -e "${BLUE}🏃 Запуск тестирования...${NC}"
python3 dialog_performance_test_redis.py \
    --users $USERS \
    --messages $MESSAGES_PER_DIALOG \
    --dialogs $DIALOGS_PER_USER

echo ""
echo -e "${GREEN}✅ Тестирование завершено!${NC}"
echo -e "${BLUE}📄 Результаты сохранены в: lesson-07/dialog_metrics_redis_udf.json${NC}" 