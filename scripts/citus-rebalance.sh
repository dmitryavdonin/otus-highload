#!/bin/bash
set -e

# Скрипт для перебалансировки шардов в кластере Citus
# Позволяет оптимизировать распределение данных между узлами

# Стратегия перебалансировки может быть задана как аргумент
# Доступные стратегии: by_shard_count (по умолчанию), by_disk_size, custom
STRATEGY=${1:-by_shard_count}

echo "Начинаем перебалансировку шардов в кластере с использованием стратегии: $STRATEGY"

# Показать текущее распределение шардов перед перебалансировкой
echo "Текущее распределение шардов:"
PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
    SELECT nodename, count(*) as shard_count
    FROM pg_dist_placement pp
    JOIN pg_dist_node pn ON pp.groupid = pn.groupid
    GROUP BY nodename
    ORDER BY nodename;
"

# Запуск процесса перебалансировки
echo "Выполняем перебалансировку..."
PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
    SELECT citus_rebalance_cluster(rebalance_strategy := '$STRATEGY');
"

# Проверка нового распределения шардов после перебалансировки
echo "Новое распределение шардов после перебалансировки:"
PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
    SELECT nodename, count(*) as shard_count
    FROM pg_dist_placement pp
    JOIN pg_dist_node pn ON pp.groupid = pn.groupid
    GROUP BY nodename
    ORDER BY nodename;
"

echo "Перебалансировка шардов завершена успешно." 