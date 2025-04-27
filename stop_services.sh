#!/bin/bash
# Script to stop all services for the social network application
# Includes PostgreSQL master/slave databases, Redis cache, and the application

echo "=== Stopping Social Network Services ==="

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

# Check if any services are running
RUNNING_CONTAINERS=$(docker-compose -f docker-compose.yml ps -q)
if [ -z "$RUNNING_CONTAINERS" ]; then
    echo "No services are currently running."
else
    # Stop the services
    echo "Stopping services..."
    docker-compose -f docker-compose.yml down

    # Check if the --volumes flag is provided to remove volumes
    if [ "$1" == "--volumes" ]; then
        echo "Removing volumes..."
        docker volume rm postgres_master_data postgres_slave1_data postgres_slave2_data redis_data
        echo "Volumes have been removed."
    fi

    echo "All services have been stopped."
fi

echo -e "\n=== Cleanup complete ==="
echo "To start services again, run: ./start_services.sh"
