#!/bin/bash
set -e

# Configure PostgreSQL to listen on all interfaces
echo "listen_addresses='*'" >> "$PGDATA/postgresql.conf"

# Allow replication connections
echo "host replication replicator all md5" >> "$PGDATA/pg_hba.conf"
echo "host all all all md5" >> "$PGDATA/pg_hba.conf"

# Create replication user and slots
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replpass';"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "SELECT * FROM pg_create_physical_replication_slot('replication_slot_slave1');"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "SELECT * FROM pg_create_physical_replication_slot('replication_slot_slave2');"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "SELECT * FROM pg_create_physical_replication_slot('replication_slot_slave3');"

# Create database if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE social_network;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "GRANT ALL PRIVILEGES ON DATABASE social_network TO replicator;"

# Create tables from schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname social_network -f /docker-entrypoint-initdb.d/schema.sql

# Configure synchronous replication
echo "# Synchronous replication settings" >> "$PGDATA/postgresql.conf"
echo "synchronous_commit = on" >> "$PGDATA/postgresql.conf"
echo "synchronous_standby_names = 'ANY 2 (slave1, slave2, slave3)'" >> "$PGDATA/postgresql.conf"

pg_ctl reload
