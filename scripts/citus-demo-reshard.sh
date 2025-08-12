#!/bin/bash
set -e

echo "==== Демонстрация решардинга без даунтайма в Citus ===="

# Функция для запуска периодических запросов к базе данных (имитирует работу приложения)
function run_background_queries() {
    echo "Запускаю периодические запросы к базе данных (имитация работы приложения)..."
    while true; do
        # Случайный запрос из набора
        QUERY_TYPE=$((RANDOM % 4))
        
        case $QUERY_TYPE in
            0)
                # Поиск пользователей
                echo -n "Выполняем запрос поиска пользователей... "
                docker-compose exec -T citus-coordinator psql -U postgres -d social_network -c "
                    SELECT COUNT(*) FROM users WHERE first_name LIKE 'Test%';
                " > /dev/null 2>&1
                echo "Выполнен"
                ;;
            1)
                # Поиск друзей
                echo -n "Выполняем запрос поиска друзей... "
                docker-compose exec -T citus-coordinator psql -U postgres -d social_network -c "
                    SELECT COUNT(*) FROM friends WHERE created_at > NOW() - INTERVAL '1 day';
                " > /dev/null 2>&1
                echo "Выполнен"
                ;;
            2)
                # Вставка данных
                echo -n "Выполняем вставку данных... "
                docker-compose exec -T citus-coordinator psql -U postgres -d social_network -c "
                    INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password, created_at)
                    VALUES (
                        gen_random_uuid(),
                        'Test User ' || (RANDOM % 1000),
                        'Surname ' || (RANDOM % 1000),
                        CURRENT_DATE - ((RANDOM % 10000) || ' days')::interval,
                        'Biography ' || (RANDOM % 1000),
                        'City ' || (RANDOM % 10),
                        'password' || (RANDOM % 1000),
                        CURRENT_TIMESTAMP
                    );
                " > /dev/null 2>&1
                echo "Выполнен"
                ;;
            3)
                # Сложный JOIN запрос
                echo -n "Выполняем JOIN запрос... "
                docker-compose exec -T citus-coordinator psql -U postgres -d social_network -c "
                    SELECT COUNT(*)
                    FROM users u
                    JOIN friends f ON u.id = f.user_id
                    WHERE u.created_at > NOW() - INTERVAL '1 day';
                " > /dev/null 2>&1
                echo "Выполнен"
                ;;
        esac
        
        # Пауза между запросами (случайная от 1 до 3 секунд)
        sleep $((RANDOM % 3 + 1))
    done
}

# Запускаем фоновые запросы
run_background_queries &
QUERIES_PID=$!

# Сохраняем PID для возможности прерывания
echo $QUERIES_PID > /tmp/citus_queries.pid

# Функция для прерывания при выходе
function cleanup() {
    echo "Завершаем работу..."
    if [ -f /tmp/citus_queries.pid ]; then
        kill $(cat /tmp/citus_queries.pid) 2>/dev/null || true
        rm /tmp/citus_queries.pid
    fi
    echo "Демонстрация завершена."
}

# Регистрируем обработчик прерывания
trap cleanup EXIT

# Информация о текущем распределении шардов
echo -e "\nТекущее распределение шардов перед решардингом:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT nodename, count(*) as shard_count
    FROM pg_dist_placement pp
    JOIN pg_dist_node pn ON pp.groupid = pn.groupid
    GROUP BY nodename
    ORDER BY nodename;
"

# Измерение производительности до решардинга
echo -e "\nИзмерение производительности до решардинга:"
START_TIME=$(date +%s.%N)

echo "-- Тест 1: Поиск пользователей"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*) FROM users WHERE first_name LIKE 'Test%';
"

echo "-- Тест 2: JOIN запрос"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*)
    FROM users u
    JOIN friends f ON u.id = f.user_id
    WHERE u.first_name LIKE 'Test%';
"

END_TIME=$(date +%s.%N)
ELAPSED_BEFORE=$(echo "$END_TIME - $START_TIME" | bc)
echo "Общее время выполнения до решардинга: $ELAPSED_BEFORE секунд"

# Имитация добавления нового узла
echo -e "\nПодготовка к добавлению нового узла в кластер..."

# Проверяем, существует ли уже узел в docker-compose.yml
if grep -q "citus-worker-4:" docker-compose.yml; then
    echo "Узел citus-worker-4 уже существует в docker-compose.yml, пропускаем его добавление."
else
    # Добавляем новый узел (citus-worker-4)
    echo "Добавляем новый рабочий узел в docker-compose.yml..."
    TEMP_FILE=$(mktemp)
    cat > $TEMP_FILE << EOF
  citus-worker-4:
    container_name: citus-worker-4
    image: citusdata/citus:12.0
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: social_network
    ports:
      - "5436:5432"
    volumes:
      - ./worker-init.sh:/docker-entrypoint-initdb.d/worker-init.sh
      - ./pg_hba.conf:/etc/postgresql/pg_hba.conf
      - citus_worker_4_data:/var/lib/postgresql/data
    networks:
      - postgres_net
    depends_on:
      citus-coordinator:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
EOF

    # Добавление нового узла в docker-compose.yml
    sed -i '/citus-worker-3:/r '$TEMP_FILE docker-compose.yml
    
    # Проверяем, существует ли том в volumes
    if ! grep -q "citus_worker_4_data:" docker-compose.yml; then
        # Добавление нового тома в секцию volumes
        sed -i '/citus_worker_3_data:/a \ \ citus_worker_4_data:\n\ \ \ \ name: citus_worker_4_data' docker-compose.yml
    fi
fi

# Проверяем, существует ли контейнер
if docker ps -a | grep -q "citus-worker-4"; then
    echo "Контейнер citus-worker-4 уже существует, проверяем его состояние..."
    if ! docker ps | grep -q "citus-worker-4"; then
        echo "Контейнер citus-worker-4 остановлен, перезапускаем..."
        docker-compose start citus-worker-4
    else
        echo "Контейнер citus-worker-4 уже запущен."
    fi
else
    echo "Запускаем новый узел..."
    docker-compose up -d citus-worker-4
fi

# Ожидание готовности нового узла
echo "Ожидаем готовности нового узла..."
while ! docker-compose exec citus-worker-4 pg_isready -U postgres -q; do
    echo "Узел citus-worker-4 еще не готов, ожидаем..."
    sleep 5
done
echo "Узел citus-worker-4 готов."

# Проверяем, добавлен ли узел в кластер Citus
NODE_EXISTS=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "
    SELECT count(*) FROM pg_dist_node WHERE nodename = 'citus-worker-4';
")

if [ "$(echo $NODE_EXISTS | tr -d '[:space:]')" = "0" ]; then
    # Добавляем новый узел в кластер Citus
    echo "Добавляем новый узел в кластер Citus..."
    docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
        SELECT * FROM citus_add_node('citus-worker-4', 5432);
        SELECT nodename, nodeport, noderole, isactive FROM pg_dist_node;
    "
else
    echo "Узел citus-worker-4 уже добавлен в кластер Citus."
    docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
        SELECT nodename, nodeport, noderole, isactive FROM pg_dist_node;
    "
fi

# Перебалансировка шардов с учетом нового узла (без даунтайма)
echo -e "\nВыполняем решардинг (перебалансировку шардов) с учетом нового узла..."
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    -- Запуск перебалансировки шардов с равномерным распределением
    SELECT citus_rebalance_cluster(rebalance_strategy := 'by_shard_count');
"

# Информация о новом распределении шардов
echo -e "\nНовое распределение шардов после решардинга:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT nodename, count(*) as shard_count
    FROM pg_dist_placement pp
    JOIN pg_dist_node pn ON pp.groupid = pn.groupid
    GROUP BY nodename
    ORDER BY nodename;
"

# Измерение производительности после решардинга
echo -e "\nИзмерение производительности после решардинга:"
START_TIME=$(date +%s.%N)

echo "-- Тест 1: Поиск пользователей"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*) FROM users WHERE first_name LIKE 'Test%';
"

echo "-- Тест 2: JOIN запрос"
docker-compose exec citus-coordinator psql -U postgres -d social_network -c "
    SELECT COUNT(*)
    FROM users u
    JOIN friends f ON u.id = f.user_id
    WHERE u.first_name LIKE 'Test%';
"

END_TIME=$(date +%s.%N)
ELAPSED_AFTER=$(echo "$END_TIME - $START_TIME" | bc)
echo "Общее время выполнения после решардинга: $ELAPSED_AFTER секунд"

# Сравнение производительности
PERF_DIFF=$(echo "$ELAPSED_BEFORE - $ELAPSED_AFTER" | bc)
if (( $(echo "$PERF_DIFF > 0" | bc -l) )); then
    echo "Производительность улучшилась на $PERF_DIFF секунд после решардинга."
elif (( $(echo "$PERF_DIFF < 0" | bc -l) )); then
    PERF_DIFF_ABS=$(echo "- $PERF_DIFF" | bc)
    echo "Производительность ухудшилась на $PERF_DIFF_ABS секунд после решардинга."
else
    echo "Производительность не изменилась после решардинга."
fi

# Ожидание ввода пользователя для завершения
echo -e "\nДемонстрация решардинга без даунтайма завершена."
echo "Нажмите CTRL+C для завершения скрипта..."

# Ожидаем, пока пользователь не прервет выполнение скрипта
wait $QUERIES_PID 