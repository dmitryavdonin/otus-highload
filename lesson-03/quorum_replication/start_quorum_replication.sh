#!/bin/bash
set -e

echo "Starting PostgreSQL Quorum Replication Cluster..."

# Clean up any existing containers and data directories
echo "Cleaning up existing containers and data directories..."
docker-compose -f docker-compose-quorum-simple.yml down -v
rm -rf pg-master-data pg-slave1-data pg-slave2-data pg-slave3-data

# Create data directories
echo "Creating data directories..."
mkdir -p pg-master-data pg-slave1-data pg-slave2-data pg-slave3-data

# Make initialization scripts executable
echo "Setting execution permissions for initialization scripts..."
chmod +x init-master.sh init-slave1.sh init-slave2.sh init-slave3.sh

# Start the cluster
echo "Starting the PostgreSQL cluster..."
docker-compose -f docker-compose-quorum-simple.yml up -d

# Wait for the master to be ready
echo "Waiting for the master to be ready..."
until docker exec pg-master pg_isready -U postgres; do
    echo "Waiting for master to be ready..."
    sleep 1
done

# Wait for the slaves to be ready
echo "Waiting for slaves to be ready..."
for slave in pg-slave1 pg-slave2 pg-slave3; do
    until docker exec $slave pg_isready -U postgres; do
        echo "Waiting for $slave to be ready..."
        sleep 1
    done
done

echo "PostgreSQL Quorum Replication Cluster is now running!"
echo "You can check the replication status with: ./check_quorum_replication.sh"
