#!/bin/bash
set -e

echo "Stopping PostgreSQL Quorum Replication Cluster..."

# Stop the cluster
docker-compose -f docker-compose-quorum-simple.yml down

echo "PostgreSQL Quorum Replication Cluster has been stopped."
echo "To remove data directories as well, run: rm -rf pg-master-data pg-slave1-data pg-slave2-data pg-slave3-data"
