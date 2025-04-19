#!/bin/bash
set -e

echo "Checking PostgreSQL Quorum Replication Status..."

# Check if containers are running
echo "Checking container status..."
docker-compose -f docker-compose-quorum-simple.yml ps

# Check replication status
echo -e "\nChecking replication status..."
docker exec pg-master psql -U postgres -c "SELECT application_name, sync_state, sync_priority FROM pg_stat_replication;"

# Check if synchronous replication is configured correctly
echo -e "\nChecking synchronous replication configuration..."
docker exec pg-master psql -U postgres -c "SHOW synchronous_standby_names;"

# Insert a test record and verify it's replicated
echo -e "\nInserting a test record on master..."
TIMESTAMP=$(date +%s)
docker exec pg-master psql -U postgres -d testdb -c "INSERT INTO test_table (data) VALUES ('Test record at $TIMESTAMP') RETURNING id, data;"

# Give some time for replication
sleep 2

# Check if the record is on all slaves
echo -e "\nVerifying record on slave1..."
docker exec pg-slave1 psql -U postgres -d testdb -c "SELECT * FROM test_table WHERE data = 'Test record at $TIMESTAMP';"

echo -e "\nVerifying record on slave2..."
docker exec pg-slave2 psql -U postgres -d testdb -c "SELECT * FROM test_table WHERE data = 'Test record at $TIMESTAMP';"

echo -e "\nVerifying record on slave3..."
docker exec pg-slave3 psql -U postgres -d testdb -c "SELECT * FROM test_table WHERE data = 'Test record at $TIMESTAMP';"

# Test quorum behavior by stopping one slave
echo -e "\nTesting quorum behavior by stopping slave3..."
docker stop pg-slave3

# Insert another record
echo -e "\nInserting another test record on master (with one slave down)..."
TIMESTAMP2=$(date +%s)
docker exec pg-master psql -U postgres -d testdb -c "INSERT INTO test_table (data) VALUES ('Test record with one slave down at $TIMESTAMP2') RETURNING id, data;"

# Give some time for replication
sleep 2

# Check if the record is on remaining slaves
echo -e "\nVerifying record on slave1..."
docker exec pg-slave1 psql -U postgres -d testdb -c "SELECT * FROM test_table WHERE data = 'Test record with one slave down at $TIMESTAMP2';"

echo -e "\nVerifying record on slave2..."
docker exec pg-slave2 psql -U postgres -d testdb -c "SELECT * FROM test_table WHERE data = 'Test record with one slave down at $TIMESTAMP2';"

# Restart the stopped slave
echo -e "\nRestarting slave3..."
docker start pg-slave3

# Wait for the slave to be ready
until docker exec pg-slave3 pg_isready -U postgres; do
    echo "Waiting for slave3 to be ready..."
    sleep 1
done

# Give some time for replication to catch up
sleep 5

# Check if the slave caught up
echo -e "\nVerifying that slave3 caught up with both records..."
docker exec pg-slave3 psql -U postgres -d testdb -c "SELECT * FROM test_table WHERE data IN ('Test record at $TIMESTAMP', 'Test record with one slave down at $TIMESTAMP2');"

echo -e "\nQuorum replication check completed!"
