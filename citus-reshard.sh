#!/bin/bash
set -e

# Скрипт для выполнения решардинга без простоя системы
# В Citus решардинг можно выполнить, добавив новые ноды и перераспределив шарды

# Имя новой ноды задается как первый аргумент при запуске скрипта
if [ $# -lt 1 ]; then
    echo "Использование: $0 <имя_новой_ноды>"
    exit 1
fi

NEW_NODE_NAME=$1
NEW_NODE_PORT=5432

echo "Начинаем процесс решардинга с добавлением новой ноды $NEW_NODE_NAME"

# Подключение к координатору
PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
    -- Добавление новой ноды в кластер
    SELECT * FROM citus_add_node('$NEW_NODE_NAME', $NEW_NODE_PORT);
    
    -- Проверка добавления ноды
    SELECT nodename, nodeport FROM pg_dist_node;
"

echo "Новая нода добавлена в кластер"

# Перебалансировка шардов на новую ноду
# Используем предложение rebalance_strategy='by_shard_count' для равномерного распределения
PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
    -- Перебалансировка шардов на основе значений распределительного столбца
    SELECT citus_rebalance_cluster(rebalance_strategy := 'by_shard_count');
"

echo "Перебалансировка шардов завершена"

# Подсчет количества шардов на каждой ноде для проверки
PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
    -- Вывод статистики распределения шардов по нодам
    SELECT nodename, count(*)
    FROM pg_dist_placement pp
    JOIN pg_dist_node pn
    ON pp.groupid = pn.groupid
    GROUP BY nodename
    ORDER BY nodename;
"

echo "Решардинг завершен успешно. Новая нода $NEW_NODE_NAME интегрирована в кластер." 