#!/bin/bash

# Script to stop the application with PostgreSQL replication
# Created by Refact Agent

echo "Stopping PostgreSQL replication setup..."

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

# Stop the containers and remove volumes
echo "Stopping containers and removing volumes..."
docker-compose -f docker-compose-replication.yml down -v

# Check if the containers have been stopped
if [ ! "$(docker ps -q -f name=postgres-master)" ] && [ ! "$(docker ps -q -f name=postgres-slave1)" ] && [ ! "$(docker ps -q -f name=postgres-slave2)" ] && [ ! "$(docker ps -q -f name=lesson-01-app)" ]; then
    echo "All containers have been stopped successfully."
else
    echo "Warning: Some containers may still be running. Please check with 'docker ps'."
    docker ps
fi

echo "PostgreSQL replication setup has been stopped."
