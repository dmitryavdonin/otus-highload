#!/bin/bash
set -e

# Stop PostgreSQL if it's running
pg_ctl stop -D "$PGDATA" -m fast || true

# Determine the replication slot name based on container name from environment
if [[ "$POSTGRES_SERVER_NAME" == "db-slave1" ]]; then
    SLOT_NAME="replication_slot_slave1"
elif [[ "$POSTGRES_SERVER_NAME" == "db-slave2" ]]; then
    SLOT_NAME="replication_slot_slave2"
else
    # Fallback to hostname-based detection
    if [[ "$HOSTNAME" == *"slave1"* || "$HOSTNAME" == *"db-slave1"* ]]; then
        SLOT_NAME="replication_slot_slave1"
    elif [[ "$HOSTNAME" == *"slave2"* || "$HOSTNAME" == *"db-slave2"* ]]; then
        SLOT_NAME="replication_slot_slave2"
    else
        # Use the container service name from Docker Compose
        if [ -f /proc/self/cgroup ]; then
            CONTAINER_NAME=$(cat /proc/self/cgroup | grep -o -e "docker/.*" | head -n 1 | sed 's/docker\///g')
            if [[ "$CONTAINER_NAME" == *"slave1"* ]]; then
                SLOT_NAME="replication_slot_slave1"
            elif [[ "$CONTAINER_NAME" == *"slave2"* ]]; then
                SLOT_NAME="replication_slot_slave2"
            else
                echo "Could not determine slave number from container name: $CONTAINER_NAME"
                # Default to slave1 if we can't determine
                SLOT_NAME="replication_slot_slave1"
            fi
        else
            echo "Could not determine slave number, defaulting to slave1"
            SLOT_NAME="replication_slot_slave1"
        fi
    fi
fi

echo "Using replication slot: $SLOT_NAME"

# Wait for master to be ready
until PGPASSWORD=postgres psql -h db-master -U postgres -d social_network -c '\q'; do
    >&2 echo "Master is unavailable - sleeping"
    sleep 1
done

>&2 echo "Master is up - executing command"

# Remove existing data directory
rm -rf "$PGDATA"/*

# Perform base backup with the specific replication slot
PGPASSWORD=replicator pg_basebackup -h db-master -U replicator -p 5432 -D "$PGDATA" -Fp -Xs -P -R -S $SLOT_NAME

# Configure standby
cat > "$PGDATA/postgresql.auto.conf" << EOF
primary_conninfo = 'host=db-master port=5432 user=replicator password=replicator application_name=${HOSTNAME}'
EOF

# Create standby signal file
touch "$PGDATA/standby.signal"

# Set proper permissions
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

# Start PostgreSQL
pg_ctl start -D "$PGDATA" -l "$PGDATA/postgresql.log" 