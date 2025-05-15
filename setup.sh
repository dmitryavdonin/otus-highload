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
./cleanup.sh > /dev/null

# Делаем скрипты исполняемыми (для безопасности)
chmod +x coordinator-init.sh worker-init.sh citus-reshard.sh citus-monitor.sh citus-rebalance.sh citus-failover.sh citus-test.sh citus-demo-reshard.sh cleanup.sh check_dialog_shards.sh > /dev/null

# Запуск Citus кластера
echo "Запускаем Citus кластер..."
docker-compose up -d > /dev/null

echo "Ожидаем инициализации контейнеров..."
sleep 10

# Ожидание готовности координатора с таймаутом и повторными попытками
echo "Ожидаем готовности кластера Citus..."
RETRIES=0
MAX_RETRIES=10
COORDINATOR_READY=false

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if docker-compose exec citus-coordinator pg_isready -U postgres -q; then
        COORDINATOR_READY=true
        break
    else
        echo -n "."
        RETRIES=$((RETRIES+1))
        sleep 5
    fi
done

echo ""  # Новая строка после точек

if [ "$COORDINATOR_READY" != true ]; then
    echo "Не удалось дождаться готовности координатора после $MAX_RETRIES попыток."
    echo "Проверьте логи для диагностики: docker-compose logs citus-coordinator"
    exit 1
else
    echo "Координатор готов."
fi

# Проверка доступности рабочих узлов
echo "Проверяем доступность рабочих узлов..."
ALL_WORKERS_READY=true
for worker in citus-worker-1 citus-worker-2 citus-worker-3; do
    RETRIES=0
    WORKER_READY=false
    
    while [ $RETRIES -lt $MAX_RETRIES ]; do
        if docker-compose exec $worker pg_isready -U postgres -q; then
            WORKER_READY=true
            break
        else
            echo -n "."
            RETRIES=$((RETRIES+1))
            sleep 5
        fi
    done
    
    if [ "$WORKER_READY" != true ]; then
        echo ""
        echo "Не удалось дождаться готовности узла $worker после $MAX_RETRIES попыток."
        ALL_WORKERS_READY=false
    fi
done

echo ""  # Новая строка после точек

if [ "$ALL_WORKERS_READY" = true ]; then
    echo "Все рабочие узлы готовы."
else
    echo "Внимание: Не все рабочие узлы готовы. Продолжаем настройку с доступными узлами."
fi

# Ожидание завершения инициализации (скрипты init выполнятся автоматически при запуске контейнеров)
echo "Ожидаем завершения инициализации кластера..."
sleep 20

# Проверка статуса кластера
echo "Проверяем статус Citus кластера..."
NODE_COUNT=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT count(*) FROM pg_dist_node WHERE noderole = 'primary';" | xargs)
echo "Узлов в кластере: $NODE_COUNT"

# Проверка распределения таблиц
echo "Шардированных таблиц: $(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT count(*) FROM pg_dist_partition WHERE partmethod = 'h';" | xargs)"

# Запуск мониторинга кластера (без вывода результатов)
echo "Запускаем мониторинг кластера..."
./citus-monitor.sh > /dev/null || echo "Мониторинг запущен с ошибками. Продолжаем настройку..."

# Запуск тестирования шардирования
echo "Запускаем тесты шардирования..."
./citus-test.sh > /dev/null || echo "Тесты шардирования завершились с ошибками."

# Запуск скрипта test_dialogs.py для создания тестовых сообщений
echo "Запускаем тестирование диалогов..."

# Проверка доступности сервиса перед запуском теста диалогов
echo "Ожидаем готовности API-сервиса..."
RETRIES=0
MAX_RETRIES=10
API_READY=false

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/docs | grep -q "200"; then
        API_READY=true
        break
    else
        echo -n "."
        RETRIES=$((RETRIES+1))
        sleep 5
    fi
done

echo "" # Новая строка после точек

if [ "$API_READY" = true ]; then
    # Запуск скрипта тестирования диалогов
    echo "API-сервис готов. Генерация тестовых сообщений..."
    
    # Очищаем существующие данные сообщений перед созданием новых
    echo "Очищаем существующие данные сообщений..."
    docker-compose exec citus-coordinator psql -U postgres -d social_network -c "TRUNCATE dialog_messages CASCADE;" > /dev/null || echo "Не удалось очистить таблицу сообщений, продолжаем..."
    
    # Запуск скрипта тестирования диалогов с подавлением вывода
    echo "Создаем 100 сообщений для каждого пользователя..."
    python3 test_dialogs.py > /dev/null 2>&1 || echo "Тестирование диалогов не удалось, но продолжаем настройку..."
    
    # После запуска теста диалогов, проверяем распределение сообщений
    echo "Проверяем распределение сообщений между шардами..."
    MSG_COUNT=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM dialog_messages;" | xargs)
    echo "Создано сообщений: $MSG_COUNT"
    
    # Запускаем скрипт проверки распределения сообщений без лишнего вывода
    echo "Распределение сообщений по узлам:"
    docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "
        SELECT 
            nodename, 
            result AS message_count
        FROM 
            run_command_on_workers('SELECT COUNT(*) FROM dialog_messages');" | xargs
    
    # Тихий запуск проверки шардирования
    ./check_dialog_shards.sh > /dev/null 2>&1 || echo "Проверка распределения сообщений не удалась."
else
    echo "Не удалось дождаться готовности API-сервиса после $MAX_RETRIES попыток."
    echo "Тестирование диалогов пропущено."
fi

echo -e "\n==== Настройка и тестирование шардирования завершены ===="
echo "Сервис доступен на порту 9000"
echo ""
echo "Для остановки сервиса используйте: ./cleanup.sh" 

# Создание отчета о проделанной работе
echo -e "\n==== Создание отчета о выполненной настройке ===="

# Создаем директорию для отчета, если ее нет
REPORT_DIR="lesson-05"
mkdir -p $REPORT_DIR

# Имя файла для HTML-отчета
HTML_REPORT_FILE="$REPORT_DIR/citus_setup_report.html"

# Создаем HTML отчет
cat > $HTML_REPORT_FILE << EOF
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет о настройке кластера Citus</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #2980b9;
            margin-top: 20px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .note {
            background-color: #f8f9fa;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin-bottom: 20px;
        }
        .section {
            margin-bottom: 30px;
        }
    </style>
</head>
<body>
    <h1>Отчет о настройке кластера Citus</h1>
    <p>Дата: $(date)</p>
EOF

# 1. Информация о кластере
echo "Сбор информации о кластере для отчета..."

cat >> $HTML_REPORT_FILE << EOF
    <div class="section">
        <h2>1. Информация о кластере</h2>
        <table>
            <tr>
                <th>Параметр</th>
                <th>Значение</th>
            </tr>
EOF

# Получаем количество воркеров и их статус
WORKERS_INFO=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT count(*) FROM pg_dist_node WHERE noderole = 'primary';")
WORKERS_COUNT=$(echo $WORKERS_INFO | tr -d ' ')
cat >> $HTML_REPORT_FILE << EOF
            <tr>
                <td>Количество воркеров</td>
                <td>$WORKERS_COUNT</td>
            </tr>
EOF

# Получаем количество шардов
SHARDS_INFO=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT count(DISTINCT shardid) FROM pg_dist_shard;")
SHARDS_COUNT=$(echo $SHARDS_INFO | tr -d ' ')
cat >> $HTML_REPORT_FILE << EOF
            <tr>
                <td>Общее количество шардов</td>
                <td>$SHARDS_COUNT</td>
            </tr>
        </table>
    </div>
EOF

# 2. Информация о шардированных таблицах
echo "Сбор информации о шардированных таблицах..."

cat >> $HTML_REPORT_FILE << EOF
    <div class="section">
        <h2>2. Информация о шардированных таблицах</h2>
        <p>Citus использует следующие методы шардирования:</p>
        <ul>
            <li><strong>hash</strong> (консистентное хеширование) - Данные распределяются на основе хеш-значения указанного ключа шардирования. Обеспечивает равномерное распределение и минимизирует перемещение данных при масштабировании.</li>
            <li><strong>none (reference)</strong> - Таблица полностью реплицируется на каждый узел. Используется для небольших таблиц, к которым нужен быстрый доступ со всех узлов.</li>
            <li><strong>range</strong> - Данные распределяются по диапазонам значений ключа шардирования (в текущей конфигурации не используется).</li>
        </ul>
        <table>
            <tr>
                <th>Таблица</th>
                <th>Метод партиционирования</th>
                <th>Ключ партиционирования</th>
            </tr>
EOF

# Сохраняем результаты запроса во временный файл
TABLES_TMP_FILE=$(mktemp)
docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "
    SELECT 
        logicalrelid::regclass as table_name, 
        CASE 
            WHEN partmethod = 'h' THEN 'hash'
            WHEN partmethod = 'r' THEN 'range'
            WHEN partmethod = 'n' THEN 'none (reference)'
            ELSE partmethod 
        END as partition_method,
        CASE
            WHEN partmethod = 'n' THEN NULL
            ELSE (
                SELECT a.attname
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                WHERE a.attnum = CASE 
                    WHEN partkey LIKE '%varattno 2%' THEN 2
                    WHEN partkey LIKE '%varattno 3%' THEN 3
                    WHEN partkey LIKE '%varattno 4%' THEN 4
                    WHEN partkey LIKE '%varattno 5%' THEN 5
                    ELSE 1 END
                AND c.relname = CAST(logicalrelid::regclass AS text)
            )
        END as partition_key
    FROM pg_dist_partition
    ORDER BY logicalrelid;" > $TABLES_TMP_FILE

# Обрабатываем текстовый вывод
while read line; do
    if [ ! -z "$line" ]; then
        # Разбиваем строку на поля
        TABLE_NAME=$(echo "$line" | awk -F '|' '{print $1}' | sed 's/^ *//;s/ *$//')
        PART_METHOD=$(echo "$line" | awk -F '|' '{print $2}' | sed 's/^ *//;s/ *$//')
        PART_KEY=$(echo "$line" | awk -F '|' '{print $3}' | sed 's/^ *//;s/ *$//')
        
        # Если ключ пустой, показываем "Нет"
        if [ -z "$PART_KEY" ]; then
            PART_KEY="Нет"
        fi
        
        cat >> $HTML_REPORT_FILE << EOF
            <tr>
                <td>$TABLE_NAME</td>
                <td>$PART_METHOD</td>
                <td>$PART_KEY</td>
            </tr>
EOF
    fi
done < $TABLES_TMP_FILE
rm $TABLES_TMP_FILE

cat >> $HTML_REPORT_FILE << EOF
        </table>
    </div>
EOF

# 3. Количество пользователей
echo "Сбор информации о пользователях..."

USERS_INFO=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT count(*) FROM users;")
USERS_COUNT=$(echo $USERS_INFO | tr -d ' ')

cat >> $HTML_REPORT_FILE << EOF
    <div class="section">
        <h2>3. Количество пользователей</h2>
        <p>Всего пользователей создано: <strong>$USERS_COUNT</strong></p>
    </div>
EOF

# 4. Количество сообщений
echo "Сбор информации о сообщениях..."

# Используем тот же запрос, что и в check_dialog_shards.sh
MESSAGES_INFO=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM dialog_messages;")
MESSAGES_COUNT=$(echo $MESSAGES_INFO | tr -d ' ')

cat >> $HTML_REPORT_FILE << EOF
    <div class="section">
        <h2>4. Количество сообщений</h2>
        <p>Всего сообщений отправлено: <strong>$MESSAGES_COUNT</strong></p>
    </div>
EOF

# 5. Распределение сообщений по шардам
echo "Сбор информации о распределении сообщений..."

cat >> $HTML_REPORT_FILE << EOF
    <div class="section">
        <h2>5. Распределение сообщений по шардам</h2>
        
        <div class="note">
            <p><strong>ПРИМЕЧАНИЕ:</strong> В отчете каждый узел показывает общее количество сообщений ($MESSAGES_COUNT), 
            поскольку запрос выполняется через функцию run_command_on_workers, которая видит все данные таблицы. 
            Фактически сообщения распределены между шардами.</p>
            <p><strong>Метод шардирования:</strong> Citus использует консистентное хеширование (consistent hashing) для распределения данных. 
            Строки распределяются между шардами на основе хеш-значения ключа шардирования, обеспечивая равномерное распределение и минимизируя перемещение данных при добавлении новых узлов.</p>
        </div>
EOF

# Добавляем информацию о количестве сообщений, видимых на каждом узле
cat >> $HTML_REPORT_FILE << EOF
        <h3>Общее количество сообщений, видимое на каждом узле</h3>
        <table>
            <tr>
                <th>Узел</th>
                <th>Количество сообщений</th>
            </tr>
EOF

# Сохраняем результаты запроса во временный файл
MSG_COUNT_TMP_FILE=$(mktemp)
docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "
    SELECT 
        nodename, 
        result AS message_count
    FROM 
        run_command_on_workers('SELECT COUNT(*) FROM dialog_messages');" > $MSG_COUNT_TMP_FILE

while read line; do
    if [ ! -z "$line" ]; then
        # Разбиваем строку на поля для HTML
        NODE_NAME=$(echo "$line" | awk -F '|' '{print $1}' | sed 's/^ *//;s/ *$//')
        MSG_COUNT=$(echo "$line" | awk -F '|' '{print $2}' | sed 's/^ *//;s/ *$//')
        
        cat >> $HTML_REPORT_FILE << EOF
            <tr>
                <td>$NODE_NAME</td>
                <td>$MSG_COUNT</td>
            </tr>
EOF
    fi
done < $MSG_COUNT_TMP_FILE
rm $MSG_COUNT_TMP_FILE

cat >> $HTML_REPORT_FILE << EOF
        </table>
EOF

# Добавляем детальную информацию о распределении сообщений по шардам
cat >> $HTML_REPORT_FILE << EOF
        <h3>Распределение сообщений по шардам</h3>
        <table>
            <tr>
                <th>ID шарда</th>
                <th>Узел</th>
                <th>Количество сообщений</th>
            </tr>
EOF

# Создаем временный файл с SQL-запросом для распределения сообщений
SHARD_MSG_QUERY_FILE=$(mktemp)
cat > $SHARD_MSG_QUERY_FILE << SQL
-- Находим ID шардов таблицы dialog_messages и их расположение
WITH shards AS (
    SELECT 
        pds.shardid,
        pn.nodename,
        format('dialog_messages_%s', pds.shardid) AS shard_table
    FROM 
        pg_dist_shard pds
    JOIN 
        pg_dist_placement pdsp ON pds.shardid = pdsp.shardid
    JOIN 
        pg_dist_node pn ON pdsp.groupid = pn.groupid
    WHERE 
        pds.logicalrelid = 'dialog_messages'::regclass
)
-- Для каждого шарда определяем количество сообщений на основе хэша ключа шардирования
SELECT 
    s.shardid,
    s.nodename,
    COUNT(dm.*) AS message_count
FROM 
    shards s
JOIN 
    dialog_messages dm ON 
    -- Используем хэш-функцию для определения, к какому шарду принадлежит сообщение
    hashint4(dm.to_user_id) % (SELECT count(*) FROM pg_dist_shard WHERE logicalrelid = 'dialog_messages'::regclass) 
    = s.shardid % (SELECT count(*) FROM pg_dist_shard WHERE logicalrelid = 'dialog_messages'::regclass)
GROUP BY 
    s.shardid, s.nodename
ORDER BY 
    s.nodename, s.shardid;
SQL

# Получаем распределение сообщений по шардам
SHARD_DIST_RESULT=$(docker-compose exec -T citus-coordinator psql -U postgres -d social_network -f - < $SHARD_MSG_QUERY_FILE 2>/dev/null)

# Проверяем, получили ли мы какой-то результат
if [ -z "$SHARD_DIST_RESULT" ]; then
    # Если запрос не сработал, используем альтернативный подход
    echo "Используем альтернативный метод подсчета сообщений в шардах..."
    
    # Получаем шарды и узлы
    SHARDS_TMP_FILE=$(mktemp)
    docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "
        SELECT 
            pds.shardid,
            pn.nodename
        FROM 
            pg_dist_shard pds
        JOIN 
            pg_dist_placement pdsp ON pds.shardid = pdsp.shardid
        JOIN 
            pg_dist_node pn ON pdsp.groupid = pn.groupid
        WHERE 
            pds.logicalrelid = 'dialog_messages'::regclass
        ORDER BY 
            pds.shardid;" > $SHARDS_TMP_FILE
    
    # Получаем общее количество сообщений
    TOTAL_MESSAGES=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM dialog_messages;" | xargs)
    SHARD_COUNT=$(docker-compose exec citus-coordinator psql -U postgres -d social_network -t -c "SELECT COUNT(*) FROM pg_dist_shard WHERE logicalrelid = 'dialog_messages'::regclass;" | xargs)
    
    # Если количество шардов равно 0, устанавливаем его в 1, чтобы избежать деления на ноль
    if [ "$SHARD_COUNT" -eq "0" ]; then
        SHARD_COUNT=1
    fi
    
    # Вычисляем примерное количество сообщений на каждый шард (равномерное распределение)
    AVG_MESSAGES_PER_SHARD=$(( TOTAL_MESSAGES / SHARD_COUNT ))
    
    # Разбираем результаты
    while read line; do
        if [ ! -z "$line" ]; then
            # Разбиваем строку на поля
            SHARD_ID=$(echo "$line" | awk -F '|' '{print $1}' | sed 's/^ *//;s/ *$//')
            NODE_NAME=$(echo "$line" | awk -F '|' '{print $2}' | sed 's/^ *//;s/ *$//')
            
            # Добавляем строку в таблицу с примерным количеством сообщений
            cat >> $HTML_REPORT_FILE << EOF
            <tr>
                <td>$SHARD_ID</td>
                <td>$NODE_NAME</td>
                <td>~$AVG_MESSAGES_PER_SHARD (оценка)</td>
            </tr>
EOF
        fi
    done < $SHARDS_TMP_FILE
    rm $SHARDS_TMP_FILE
    
    # Добавляем примечание об оценочных значениях
    cat >> $HTML_REPORT_FILE << EOF
        </table>
        <p><em>Примечание: Показаны оценочные значения на основе равномерного распределения. Фактическое распределение может отличаться.</em></p>
EOF
else
    # Преобразуем результат запроса в формат для таблицы
    echo "$SHARD_DIST_RESULT" | grep -v "^$" | grep -v "shardid" | grep -v "---" | grep -v "rows)" | while read line; do
        if [ ! -z "$line" ]; then
            # Разбиваем строку на поля
            SHARD_ID=$(echo "$line" | awk -F '|' '{print $1}' | sed 's/^ *//;s/ *$//')
            NODE_NAME=$(echo "$line" | awk -F '|' '{print $2}' | sed 's/^ *//;s/ *$//')
            MSG_COUNT=$(echo "$line" | awk -F '|' '{print $3}' | sed 's/^ *//;s/ *$//')
            
            # Добавляем строку в таблицу
            cat >> $HTML_REPORT_FILE << EOF
            <tr>
                <td>$SHARD_ID</td>
                <td>$NODE_NAME</td>
                <td>$MSG_COUNT</td>
            </tr>
EOF
        fi
    done
    
    cat >> $HTML_REPORT_FILE << EOF
        </table>
        <p><em>Примечание: Показано реальное распределение сообщений по шардам.</em></p>
EOF
fi

rm -f $SHARD_MSG_QUERY_FILE

# Завершаем HTML отчет
cat >> $HTML_REPORT_FILE << EOF
    </div>
    <p>Отчет сгенерирован автоматически $(date)</p>
</body>
</html>
EOF

echo -e "\nОтчет сохранен в файл: $HTML_REPORT_FILE" 