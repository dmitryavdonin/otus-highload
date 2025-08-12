#!/bin/bash
set -e

# Скрипт для обработки отказа узла в кластере Citus
# Позволяет деактивировать сбойный узел и перераспределить его шарды на активные узлы

# Имя узла с ошибкой задается как первый аргумент
if [ $# -lt 1 ]; then
    echo "Использование: $0 <имя_сбойного_узла>"
    exit 1
fi

FAILED_NODE=$1

echo "Начинаем обработку отказа узла: $FAILED_NODE"

# Проверяем, существует ли указанный узел
NODE_EXISTS=$(PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -t -c "
    SELECT COUNT(*) FROM pg_dist_node WHERE nodename = '$FAILED_NODE';
")

if [ $NODE_EXISTS -eq 0 ]; then
    echo "Ошибка: узел $FAILED_NODE не найден в кластере."
    exit 1
fi

# Проверяем статус узла
NODE_STATUS=$(PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -t -c "
    SELECT isactive FROM pg_dist_node WHERE nodename = '$FAILED_NODE';
")

if [ "$NODE_STATUS" == " f" ]; then
    echo "Узел $FAILED_NODE уже отмечен как неактивный."
else
    # Деактивируем сбойный узел
    echo "Деактивируем узел $FAILED_NODE..."
    PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
        SELECT * FROM citus_disable_node('$FAILED_NODE', 5432);
    "
    
    # Проверяем статус активных узлов
    echo "Список активных узлов после деактивации:"
    PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
        SELECT nodename, nodeport, noderole, isactive 
        FROM pg_dist_node;
    "
    
    # Перебалансировка шардов между оставшимися активными узлами
    echo "Перебалансируем шарды между оставшимися активными узлами..."
    PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
        SELECT citus_rebalance_cluster(rebalance_strategy := 'by_shard_count');
    "
    
    # Проверка нового распределения шардов после перебалансировки
    echo "Новое распределение шардов после перебалансировки:"
    PGPASSWORD=postgres psql -h citus-coordinator -U postgres -d social_network -c "
        SELECT nodename, count(*) as shard_count
        FROM pg_dist_placement pp
        JOIN pg_dist_node pn ON pp.groupid = pn.groupid
        WHERE pn.isactive = true
        GROUP BY nodename
        ORDER BY nodename;
    "
fi

echo "Обработка отказа узла $FAILED_NODE завершена." 