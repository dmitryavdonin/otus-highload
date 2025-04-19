#!/bin/bash
# Script to stop the application and PostgreSQL replication

echo "=== Stopping PostgreSQL Replication and Application ==="

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

# Check if any services are running
RUNNING_CONTAINERS=$(docker-compose -f docker-compose-replication.yml ps -q)
if [ -z "$RUNNING_CONTAINERS" ]; then
    echo "No services are currently running."
else
    # Stop the services
    echo "Stopping services..."
    docker-compose -f docker-compose-replication.yml down

    # Check if the --volumes flag is provided to remove volumes
    if [ "$1" == "--volumes" ]; then
        echo "Removing volumes..."
        docker volume rm postgres_master_data postgres_slave1_data postgres_slave2_data
        echo "Volumes have been removed."
    fi

    echo "All services have been stopped."
fi

echo -e "\n=== Cleanup complete ==="
echo "To start services again, run: ./start_replication.sh"
