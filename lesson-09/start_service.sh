#!/bin/bash

echo "Запуск отказоустойчивой системы социальной сети"
echo "=============================================="

# Проверка наличия Docker
echo "Проверка Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "Установка Docker..."
    sudo apt update
    sudo apt install -y docker.io docker-compose-plugin
    sudo usermod -aG docker $USER
    sudo systemctl start docker
    sudo systemctl enable docker
    echo "✅ Docker установлен. Перезайдите в систему для применения прав группы docker"
    exit 1
fi

# Проверка наличия Python библиотек
echo "Проверка Python библиотек..."
if ! python3 -c "import aiohttp" &> /dev/null; then
    echo "Установка Python библиотек..."
    sudo apt install -y python3-aiohttp
fi



# Запуск системы
echo "Запуск Docker Compose..."
docker compose -f docker-compose-ha.yml up -d

# Ожидание запуска сервисов
echo "Ожидание запуска всех сервисов..."
sleep 30

# Проверка состояния сервисов
echo "Проверка состояния сервисов..."
docker compose -f docker-compose-ha.yml ps

# Проверка доступности компонентов
echo ""
echo "Проверка доступности компонентов..."

echo -n "Nginx (HTTP балансировщик): "
if curl -s http://localhost/health > /dev/null; then
    echo "✅ OK"
else
    echo "❌ НЕДОСТУПЕН"
fi

echo -n "HAProxy статистика: "
if curl -s http://localhost:8404/stats > /dev/null; then
    echo "✅ OK"
else
    echo "❌ НЕДОСТУПЕН"
fi

echo -n "PostgreSQL мастер: "
if docker exec lesson-09-postgres-master-1 pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ OK"
else
    echo "❌ НЕДОСТУПЕН"
fi

echo -n "PostgreSQL слейв 1: "
if docker exec lesson-09-postgres-slave1-1 pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ OK"
else
    echo "❌ НЕДОСТУПЕН"
fi

echo -n "PostgreSQL слейв 2: "
if docker exec lesson-09-postgres-slave2-1 pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ OK"
else
    echo "❌ НЕДОСТУПЕН"
fi

echo ""
echo "✅ Система запущена!"
echo ""
echo "Доступные интерфейсы:"
echo "   • Приложение: http://localhost"
echo "   • HAProxy статистика: http://localhost:8404/stats"
echo "   • Health check: http://localhost/health"
echo ""
echo "Для тестирования запустите: ./test_service.sh"
echo "Для остановки запустите: ./stop_service.sh" 