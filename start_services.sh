#!/bin/bash
# Script to start all services for the social network application
# Includes PostgreSQL master/slave databases, Redis cache, and the application

echo "=== Starting Social Network Services ==="

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed. Please install it first."
    exit 1
fi

# Check if the docker-compose file exists
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: docker-compose.yml not found in the current directory."
    exit 1
fi

# Stop any existing containers to avoid conflicts
echo "Stopping any existing containers..."
docker-compose -f docker-compose.yml down

# Remove existing volumes if requested
if [ "$1" == "--clean" ]; then
    echo "Removing existing volumes..."
    docker volume rm postgres_master_data postgres_slave1_data postgres_slave2_data redis_data
fi

# Start the services
echo "Starting services..."
docker-compose -f docker-compose.yml build app
docker-compose -f docker-compose.yml up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Check if all services are running
echo "Checking service status..."
SERVICES="db-master db-slave1 db-slave2 redis app"
ALL_RUNNING=true

for SERVICE in $SERVICES; do
    if ! docker ps | grep -q "otus-highload-$SERVICE"; then
        echo "Service $SERVICE is not running."
        echo "Checking logs for $SERVICE:"
        docker-compose -f docker-compose.yml logs $SERVICE | tail -n 20
        ALL_RUNNING=false
    else
        echo "Service $SERVICE is running."
    fi
done

if [ "$ALL_RUNNING" = false ]; then
    echo "Some services failed to start. You can check detailed logs with: docker-compose -f docker-compose.yml logs"
    echo "Do you want to continue anyway? (y/n)"
    read -r CONTINUE
    if [[ "$CONTINUE" != "y" && "$CONTINUE" != "Y" ]]; then
        exit 1
    fi
fi

# Wait a bit more for replication to be established
echo "Waiting for replication to be established..."
sleep 20

# Check replication status
#echo "Checking replication status..."
#./check_replication_status.sh

echo -e "\n=== All services are up and running ==="
echo "Master database is available at localhost:5432"
echo "Slave1 database is available at localhost:5433"
echo "Slave2 database is available at localhost:5434"
echo "Redis is available at localhost:6379"
echo "Application is available at localhost:9000"
echo -e "\nTo check logs, run: docker-compose -f docker-compose.yml logs [service_name]"
echo "To stop all services, run: ./stop_services.sh"
echo "To check replication status run: ./check_replication_status.sh"
