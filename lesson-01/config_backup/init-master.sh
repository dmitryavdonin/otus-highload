#!/bin/bash
set -e

# Configure PostgreSQL to listen on all interfaces
echo "listen_addresses='*'" >> "$PGDATA/postgresql.conf"

# Allow replication connections
echo "host replication replicator all md5" >> "$PGDATA/pg_hba.conf"
echo "host all all all md5" >> "$PGDATA/pg_hba.conf"

# Create replication user and slots
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replicator';"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "GRANT ALL PRIVILEGES ON DATABASE social_network TO replicator;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "SELECT * FROM pg_create_physical_replication_slot('replication_slot_slave1');"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "SELECT * FROM pg_create_physical_replication_slot('replication_slot_slave2');"

# Create tables from schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/schema.sql

pg_ctl reload 