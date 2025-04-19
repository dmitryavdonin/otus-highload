#!/bin/bash
# Script to start the application and PostgreSQL replication

echo "=== Starting PostgreSQL Replication and Application ==="

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed. Please install it first."
    exit 1
fi

# Check if the docker-compose file exists
if [ ! -f "docker-compose-replication.yml" ]; then
    echo "Error: docker-compose-replication.yml not found in the current directory."
    exit 1
fi

# Stop any existing containers to avoid conflicts
echo "Stopping any existing containers..."
docker-compose -f docker-compose-replication.yml down

# Remove existing volumes if requested
if [ "$1" == "--clean" ]; then
    echo "Removing existing volumes..."
    docker volume rm postgres_master_data postgres_slave1_data postgres_slave2_data
fi

# Start the services
echo "Starting services..."
docker-compose -f docker-compose-replication.yml up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Check if all services are running
echo "Checking service status..."
SERVICES=$(docker-compose -f docker-compose-replication.yml ps --services)
ALL_RUNNING=true

for SERVICE in $SERVICES; do
    STATUS=$(docker-compose -f docker-compose-replication.yml ps $SERVICE | grep -v "Name" | awk '{print $4}')
    if [[ "$STATUS" != "Up" && "$STATUS" != "Up ("* ]]; then
        echo "Service $SERVICE is not running. Status: $STATUS"
        ALL_RUNNING=false
    else
        echo "Service $SERVICE is running."
    fi
done

if [ "$ALL_RUNNING" = false ]; then
    echo "Some services failed to start. Check the logs with: docker-compose -f docker-compose-replication.yml logs"
    exit 1
fi

# Wait a bit more for replication to be established
echo "Waiting for replication to be established..."
sleep 20

# Check replication status
echo "Checking replication status..."
./check_replication_status.sh

echo -e "\n=== All services are up and running ==="
echo "Master database is available at localhost:5432"
echo "Slave1 database is available at localhost:5433"
echo "Slave2 database is available at localhost:5434"
echo "Application is available at localhost:9000"
echo -e "\nTo check logs, run: docker-compose -f docker-compose-replication.yml logs [service_name]"
echo "To stop all services, run: docker-compose -f docker-compose-replication.yml down"
echo "To check replication status again, run: ./check_replication_status.sh"
