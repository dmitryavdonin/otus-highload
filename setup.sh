#!/bin/bash
# Отключаем строгую проверку ошибок для более гибкой обработки проблем
set +e

echo "==== Запуск настройки шардирования с Citus ===="

# Проверка наличия Docker и Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Docker не установлен. Установите Docker перед запуском скрипта."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose не установлен. Установите Docker Compose перед запуском скрипта."
    exit 1
fi

# Сначала запустим скрипт очистки для удаления существующих контейнеров и данных
echo "Запускаем скрипт очистки для подготовки среды..."
./cleanup.sh

# Делаем скрипты исполняемыми (для безопасности)
echo "Делаем скрипты исполняемыми..."
chmod +x coordinator-init.sh worker-init.sh citus-reshard.sh citus-monitor.sh citus-rebalance.sh citus-failover.sh citus-test.sh citus-demo-reshard.sh cleanup.sh

# Запуск Citus кластера
echo "Запускаем Citus кластер..."
docker-compose up -d

echo "Ожидаем инициализации контейнеров..."
sleep 10

# Ожидание готовности координатора с таймаутом и повторными попытками
echo "Ожидаем готовности координатора Citus..."
RETRIES=0
MAX_RETRIES=10
COORDINATOR_READY=false

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if docker-compose exec citus-coordinator pg_isready -U postgres -q; then
        COORDINATOR_READY=true
        echo "Координатор готов."
        break
    else
        echo "Координатор еще не готов, повторная попытка $((RETRIES+1))/$MAX_RETRIES..."
        RETRIES=$((RETRIES+1))
        sleep 10
    fi
done

if [ "$COORDINATOR_READY" != true ]; then
    echo "Не удалось дождаться готовности координатора после $MAX_RETRIES попыток."
    echo "Проверьте логи для диагностики: docker-compose logs citus-coordinator"
    exit 1
fi

# Проверка доступности рабочих узлов
echo "Проверяем доступность рабочих узлов..."
for worker in citus-worker-1 citus-worker-2 citus-worker-3; do
    RETRIES=0
    WORKER_READY=false
    
    while [ $RETRIES -lt $MAX_RETRIES ]; do
        if docker-compose exec $worker pg_isready -U postgres -q; then
            WORKER_READY=true
            echo "Узел $worker готов."
            break
        else
            echo "Узел $worker еще не готов, повторная попытка $((RETRIES+1))/$MAX_RETRIES..."
            RETRIES=$((RETRIES+1))
            sleep 10
        fi
    done
    
    if [ "$WORKER_READY" != true ]; then
        echo "Не удалось дождаться готовности узла $worker после $MAX_RETRIES попыток."
        echo "Проверьте логи для диагностики: docker-compose logs $worker"
        echo "Продолжаем настройку с доступными узлами..."
    fi
done

# Ожидание завершения инициализации (скрипты init выполнятся автоматически при запуске контейнеров)
echo "Ожидаем завершения инициализации кластера..."
sleep 20

# Проверка статуса кластера
echo "Проверяем статус Citus кластера..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "SELECT nodename, nodeport, noderole FROM pg_dist_node;" || {
    echo "Не удалось получить информацию о кластере. Возможно, инициализация не завершена."
    echo "Проверьте логи: docker-compose logs"
    exit 1
}

# Проверка распределения таблиц
echo "Проверяем распределение таблиц..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT logicalrelid::regclass, partmethod, partkey
    FROM pg_dist_partition
    ORDER BY logicalrelid;
" || echo "Не удалось получить информацию о распределении таблиц."

# Запуск мониторинга кластера
echo "Запускаем мониторинг кластера..."
./citus-monitor.sh || echo "Мониторинг не удался. Продолжаем настройку..."

# Запуск тестирования шардирования
echo -e "\n==== Тестирование шардирования ===="
echo "Запускаем тесты для проверки работоспособности шардирования..."
./citus-test.sh || echo "Тесты шардирования не удались."

echo -e "\n==== Настройка и тестирование шардирования завершены ===="
echo "Сервис доступен на порту 9000"
echo ""
echo "Полезные команды:"
echo "  ./citus-monitor.sh - мониторинг состояния кластера"
echo "  ./citus-rebalance.sh - перебалансировка шардов"
echo "  ./citus-reshard.sh <имя_новой_ноды> - добавление новой ноды и решардинг"
echo "  ./citus-failover.sh <имя_сбойного_узла> - обработка отказа узла"
echo "  ./citus-test.sh - повторное тестирование шардирования"
echo "  ./citus-demo-reshard.sh - демонстрация решардинга без даунтайма"
echo "  ./cleanup.sh - остановка кластера и возврат в исходное состояние"
echo ""
echo "Для остановки сервиса используйте: ./cleanup.sh" 