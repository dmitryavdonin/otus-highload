#!/bin/bash

# Скрипт для проверки статуса всех сервисов DZ-10

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
COMPOSE_FILE="../../deploy/docker/docker-compose.yml"

# Проверяем наличие docker compose
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v "docker-compose" >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "docker compose/docker-compose is not installed" >&2
  exit 1
fi

echo -e "${BLUE}=== Статус сервисов DZ-10 ===${NC}"
echo ""

# Функция для проверки статуса контейнера
check_container() {
  local container_name="$1"
  local service_name="$2"
  
  if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$container_name"; then
    local status=$(docker ps --format "{{.Status}}" --filter "name=$container_name")
    if echo "$status" | grep -q "healthy\|Up"; then
      echo -e "  ${GREEN}✓${NC} $service_name: $status"
      return 0
    else
      echo -e "  ${RED}✗${NC} $service_name: $status"
      return 1
    fi
  else
    echo -e "  ${RED}✗${NC} $service_name: Не запущен"
    return 1
  fi
}

# Функция для проверки HTTP endpoint
check_http() {
  local url="$1"
  local service_name="$2"
  
  if curl -s -f "$url" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} $service_name Health Check: OK"
    return 0
  else
    echo -e "  ${RED}✗${NC} $service_name Health Check: FAIL"
    return 1
  fi
}

# Проверяем контейнеры
echo -e "${YELLOW}Статус контейнеров:${NC}"
check_container "docker-postgres-1" "PostgreSQL Database"
check_container "docker-redis-1" "Redis Cache"
check_container "docker-rabbitmq-1" "RabbitMQ Message Broker"
check_container "docker-dialog-service-1" "Dialog Service"
check_container "docker-counter-service-1" "Counter Service"
check_container "docker-monolith-1" "Main API Service"
check_container "docker-nginx-1" "Nginx Proxy"

echo ""

# Проверяем HTTP endpoints
echo -e "${YELLOW}Проверка HTTP endpoints:${NC}"
check_http "http://localhost:8000/health" "Main API (8000)"
check_http "http://localhost:8002/health" "Dialog Service (8002)"
check_http "http://localhost:8003/health" "Counter Service (8003)"
check_http "http://localhost:8080/health" "Nginx Proxy (8080)" || check_http "http://localhost:80/health" "Nginx Proxy (80)"

echo ""

# Показываем логи проблемных контейнеров
echo -e "${YELLOW}Проверка проблемных сервисов:${NC}"
for container in docker-dialog-service-1 docker-counter-service-1 docker-monolith-1; do
  if ! docker ps --filter "name=$container" --filter "status=running" | grep -q "$container"; then
    echo -e "${RED}$container не запущен. Последние логи:${NC}"
    echo "----------------------------------------"
    docker logs "$container" --tail 10 2>/dev/null || echo "Контейнер не найден"
    echo "----------------------------------------"
    echo ""
  fi
done

# Проверяем RabbitMQ Management UI
echo -e "${YELLOW}Дополнительные проверки:${NC}"
if curl -s "http://localhost:15672" >/dev/null 2>&1; then
  echo -e "  ${GREEN}✓${NC} RabbitMQ Management UI доступен: http://localhost:15672"
  echo -e "    ${BLUE}ℹ${NC} Логин: admin, Пароль: admin123"
else
  echo -e "  ${RED}✗${NC} RabbitMQ Management UI недоступен"
fi

# Проверяем что Docker Compose запущен
echo ""
echo -e "${YELLOW}Статус Docker Compose:${NC}"
if $DC -f "$COMPOSE_FILE" ps --format table | grep -q "Up\|healthy"; then
  echo -e "${GREEN}Docker Compose сервисы запущены:${NC}"
  $DC -f "$COMPOSE_FILE" ps --format table
else
  echo -e "${RED}Docker Compose сервисы не запущены${NC}"
fi

echo ""
echo -e "${BLUE}=== Команды для диагностики ===${NC}"
echo "Логи всех сервисов:       $DC -f $COMPOSE_FILE logs"
echo "Логи Dialog Service:      docker logs docker-dialog-service-1"
echo "Логи Counter Service:     docker logs docker-counter-service-1"
echo "Перезапуск всех сервисов: ./stop_service.sh && ./start_service.sh"
echo "Запуск тестов:            python3 test_counters.py"
