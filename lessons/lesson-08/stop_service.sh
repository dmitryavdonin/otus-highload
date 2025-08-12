#!/bin/bash

# ==============================================================================
# Скрипт для остановки всех сервисов, запущенных через docker-compose (ДЗ-8)
# ==============================================================================

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="deploy/docker/docker-compose.yml"

echo -e "${BLUE}🚀 Остановка всех сервисов, запущенных через docker-compose...${NC}"
echo "=================================================="

# Проверка наличия Docker и Docker Compose
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker или Docker Compose не установлены.${NC}"
    exit 1
fi

# Выполняем docker-compose down
docker-compose -f $COMPOSE_FILE down --remove-orphans

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Произошла ошибка при остановке сервисов.${NC}"
    exit 1
fi

echo "=================================================="
echo -e "${GREEN}✅ Все сервисы успешно остановлены и удалены.${NC}"
echo "" 