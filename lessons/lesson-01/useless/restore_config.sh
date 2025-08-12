#!/bin/bash
set -e

echo "Stopping containers..."
docker compose -f lesson-01/docker-compose.yml down

echo "Restoring configuration files from backup..."
cp lesson-01/config_backup/* lesson-01/

echo "Setting correct permissions..."
chmod +x lesson-01/start-slave.sh
chmod +x lesson-01/init-master.sh

echo "Starting containers with restored configuration..."
docker compose -f lesson-01/docker-compose.yml up -d

echo "Waiting for services to start..."
sleep 10

echo "Checking replication status..."
docker compose -f lesson-01/docker-compose.yml exec -T db-master psql -U postgres -c "SELECT * FROM pg_stat_replication;"

echo "Configuration restored and services restarted!"
echo "Check the logs if needed:"
echo "docker compose -f lesson-01/docker-compose.yml logs db-master"
echo "docker compose -f lesson-01/docker-compose.yml logs db-slave1"
echo "docker compose -f lesson-01/docker-compose.yml logs db-slave2" 