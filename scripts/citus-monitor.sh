#!/bin/bash
set -e

echo "==== Мониторинг кластера Citus ===="

echo -e "\n1. Проверка узлов в кластере:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT nodeid, groupid, nodename, nodeport, noderole, isactive 
    FROM pg_dist_node;
"

echo -e "\n2. Распределение шардов по узлам:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT nodename, count(*) as shard_count
    FROM pg_dist_placement pp
    JOIN pg_dist_node pn ON pp.groupid = pn.groupid
    GROUP BY nodename
    ORDER BY nodename;
"

echo -e "\n3. Информация о распределенных таблицах:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT logicalrelid::regclass, partmethod, partkey, colocationid, repmodel
    FROM pg_dist_partition
    ORDER BY logicalrelid;
"

echo -e "\n4. Детали шардов для таблиц:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT
        logicalrelid::regclass AS table_name,
        count(DISTINCT shardid) AS shard_count
    FROM pg_dist_shard
    GROUP BY logicalrelid
    ORDER BY table_name;
"

echo -e "\n5. Проверка статуса подключений к рабочим узлам:"
docker-compose exec citus-coordinator psql -U postgres -d social_network -P pager=off -c "
    SELECT nodename, result
    FROM run_command_on_workers('
        SELECT
            current_database() as database,
            inet_server_addr() as ip,
            inet_server_port() as port,
            pg_postmaster_start_time() as start_time
    ');
"

echo -e "\n==== Мониторинг завершен ====" 