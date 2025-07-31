#!/bin/bash

echo "Остановка системы..."

# Остановка и удаление всех контейнеров, volumes и сетей
docker compose -f docker-compose-ha.yml down --volumes --remove-orphans

# Очистка системы Docker от неиспользуемых ресурсов
docker system prune -f > /dev/null 2>&1

# Удаление файлов логов тестирования
if [ -f test_results.log ]; then
    rm -f test_results.log
fi

echo "✅ Система остановлена" 