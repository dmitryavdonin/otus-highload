#!/bin/bash
set -e

# Stop PostgreSQL if it's running and wait for it to stop
if pg_ctl status -D "$PGDATA" > /dev/null 2>&1; then
    pg_ctl stop -D "$PGDATA" -m fast
    while pg_ctl status -D "$PGDATA" > /dev/null 2>&1; do
        sleep 1
    done
fi

# Wait for master to be ready
until PGPASSWORD=postgres psql -h db-master -U postgres -d postgres -c '\q'; do
    >&2 echo "Master is unavailable - sleeping"
    sleep 1
done

>&2 echo "Master is up - executing command"

# Remove existing data directory
rm -rf "$PGDATA"/*

# Perform base backup
PGPASSWORD=replpass pg_basebackup -h db-master -U replicator -p 5432 -D "$PGDATA" -Fp -Xs -P

# Configure standby
cat > "$PGDATA/postgresql.auto.conf" << EOF
primary_conninfo = 'host=db-master port=5432 user=replicator password=replpass application_name=${HOSTNAME}'
hot_standby = on
EOF

# Create standby signal file
touch "$PGDATA/standby.signal"

# Set proper permissions
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

# Start PostgreSQL
pg_ctl start -D "$PGDATA" -l "$PGDATA/postgresql.log"
