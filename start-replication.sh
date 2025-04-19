#!/bin/bash

# Script to start the application with PostgreSQL replication
# Created by Refact Agent

echo "Starting PostgreSQL replication setup..."

# Navigate to the project directory
cd "$(dirname "$0")"

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

# Create necessary directories if they don't exist
mkdir -p pg_master_data pg_slave1_data pg_slave2_data

# Stop any existing containers and remove volumes
echo "Stopping any existing containers..."
docker-compose -f docker-compose-replication.yml down -v

# Start the containers
echo "Starting containers with PostgreSQL replication..."
docker-compose -f docker-compose-replication.yml up -d

# Wait for the containers to be ready
echo "Waiting for containers to be ready..."
sleep 10

# Check if the containers are running
if [ "$(docker ps -q -f name=postgres-master)" ] && [ "$(docker ps -q -f name=postgres-slave1)" ] && [ "$(docker ps -q -f name=postgres-slave2)" ] && [ "$(docker ps -q -f name=lesson-01-app)" ]; then
    echo "All containers are running."
    
    # Check replication status
    echo "Checking replication status..."
    docker exec postgres-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"
    
    echo "PostgreSQL replication setup completed successfully."
    echo "The application is now running with PostgreSQL replication."
    echo "You can access the application at http://localhost:9000"
else
    echo "Error: Some containers failed to start. Please check the logs."
    docker-compose -f docker-compose-replication.yml logs
    exit 1
fi
