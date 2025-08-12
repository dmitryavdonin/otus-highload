#!/bin/bash
# Script to check PostgreSQL replication status

echo "=== Checking Master Replication Status ==="
echo "Replication connections:"
docker-compose -f docker-compose.yml exec db-master psql -U postgres -c "SELECT * FROM pg_stat_replication;"

echo -e "\nReplication slots:"
docker-compose -f docker-compose.yml exec db-master psql -U postgres -c "SELECT * FROM pg_replication_slots;"

echo -e "\n=== Checking Slave1 Status ==="
echo "Is in recovery mode:"
docker-compose -f docker-compose.yml exec db-slave1 psql -U postgres -c "SELECT pg_is_in_recovery();"

echo -e "\nReceive location:"
docker-compose -f docker-compose.yml exec db-slave1 psql -U postgres -c "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(), pg_last_xact_replay_timestamp();"

echo -e "\n=== Checking Slave2 Status ==="
echo "Is in recovery mode:"
docker-compose -f docker-compose.yml exec db-slave2 psql -U postgres -c "SELECT pg_is_in_recovery();"

echo -e "\nReceive location:"
docker-compose -f docker-compose.yml exec db-slave2 psql -U postgres -c "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(), pg_last_xact_replay_timestamp();"
