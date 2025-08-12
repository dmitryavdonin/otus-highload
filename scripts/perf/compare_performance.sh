#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 Сравнение производительности PostgreSQL vs Redis${NC}"
echo "=================================================="

# Проверяем наличие файлов результатов
if [ ! -f "lesson-07/dialog_metrics_postgresql.json" ]; then
    echo -e "${RED}❌ Файл результатов PostgreSQL не найден${NC}"
    echo "Запустите тест: ./run_dialog_performance_test.sh"
    exit 1
fi

if [ ! -f "lesson-07/dialog_metrics_redis.json" ]; then
    echo -e "${RED}❌ Файл результатов Redis не найден${NC}"
    echo "Запустите тест: ./run_dialog_performance_test_redis.sh"
    exit 1
fi

# Проверяем наличие виртуального окружения
VENV_DIR="./venv"
if [ -d "$VENV_DIR" ]; then
    echo -e "${BLUE}🐍 Активация виртуального окружения...${NC}"
    source "$VENV_DIR/bin/activate"
else
    echo -e "${YELLOW}⚠️  Виртуальное окружение не найдено, используем системный Python${NC}"
fi

# Запускаем сравнение
echo -e "${BLUE}🔍 Анализ результатов...${NC}"
python3 compare_performance.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Сравнение завершено успешно!${NC}"
else
    echo ""
    echo -e "${RED}❌ Ошибка при сравнении результатов${NC}"
    exit 1
fi 