#!/bin/bash
# Отключаем строгую проверку ошибок, чтобы скрипт продолжался даже при возникновении ошибок
set +e

echo "==== Остановка кластера Citus и возврат в исходное состояние ===="

# Проверка, запущены ли контейнеры
echo "Проверка статуса контейнеров..."
RUNNING_CONTAINERS=$(docker-compose ps --services --filter "status=running" 2>/dev/null | grep -c "citus" || echo "0")

if [ "$RUNNING_CONTAINERS" -eq 0 ]; then
    echo "Активные контейнеры Citus не обнаружены."
else
    echo "Обнаружено активных контейнеров Citus: $RUNNING_CONTAINERS"
    
    # Остановка всех контейнеров
    echo "Останавливаем контейнеры..."
    docker-compose down
fi

# Проверяем наличие измененного docker-compose.yml
if grep -q "citus-worker-4" docker-compose.yml 2>/dev/null; then
    echo "Обнаружены изменения в docker-compose.yml (добавлен citus-worker-4)."
    echo "Удаляем дополнительные узлы..."
    
    # Создаем резервную копию текущего файла
    cp docker-compose.yml docker-compose.yml.bak
    
    # Удаляем блок citus-worker-4 (универсальный подход)
    sed -i '/citus-worker-4:/,/healthcheck:/d' docker-compose.yml 2>/dev/null
    
    # Удаляем том citus_worker_4_data
    sed -i '/citus_worker_4_data:/d' docker-compose.yml 2>/dev/null
    sed -i '/name: citus_worker_4_data/d' docker-compose.yml 2>/dev/null
    
    echo "Файл docker-compose.yml восстановлен в исходное состояние."
    echo "Резервная копия сохранена как docker-compose.yml.bak"
fi

# Удаление данных томов без sudo, если возможно
echo "Удаление данных томов..."
rm -rf citus_coordinator_data citus_worker_1_data citus_worker_2_data citus_worker_3_data citus_worker_4_data 2>/dev/null || {
    echo "Не удалось удалить директории томов без sudo. Попробуем с sudo..."
    sudo rm -rf citus_coordinator_data citus_worker_1_data citus_worker_2_data citus_worker_3_data citus_worker_4_data 2>/dev/null
}

# Удаление временных файлов
echo "Удаление временных файлов..."
rm -f /tmp/citus_queries.pid 2>/dev/null

# Проверка и удаление контейнеров
echo "Удаление контейнеров Citus..."
CITUS_CONTAINERS=$(docker ps -a -q --filter "name=citus")
if [ ! -z "$CITUS_CONTAINERS" ]; then
    docker rm -f $CITUS_CONTAINERS 2>/dev/null
    echo "Контейнеры Citus удалены."
else
    echo "Контейнеры Citus не обнаружены."
fi

# Проверка и удаление томов
echo "Удаление томов Citus..."
CITUS_VOLUMES=$(docker volume ls -q | grep "citus")
if [ ! -z "$CITUS_VOLUMES" ]; then
    docker volume rm $CITUS_VOLUMES 2>/dev/null
    echo "Тома Citus удалены."
else
    echo "Тома Citus не обнаружены."
fi

# Удаление dangling volumes
echo "Проверка и удаление dangling volumes..."
DANGLING_VOLUMES=$(docker volume ls -qf dangling=true)
if [ ! -z "$DANGLING_VOLUMES" ]; then
    docker volume rm $DANGLING_VOLUMES 2>/dev/null
    echo "Dangling volumes удалены."
else
    echo "Dangling volumes не обнаружены."
fi

echo "==== Кластер остановлен и приведен в исходное состояние ===="
echo "Для повторного запуска кластера используйте: ./setup.sh" 