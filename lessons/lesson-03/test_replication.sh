#!/bin/bash
# Script to test PostgreSQL replication by inserting data and checking it on slaves

echo "=== Creating test table on master ==="
docker-compose -f docker-compose-replication.yml exec db-master psql -U postgres -d social_network -c "
CREATE TABLE IF NOT EXISTS replication_test (
    id SERIAL PRIMARY KEY,
    test_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"

echo -e "\n=== Inserting test data on master ==="
TEST_DATA="Test data inserted at $(date)"
docker-compose -f docker-compose-replication.yml exec db-master psql -U postgres -d social_network -c "
INSERT INTO replication_test (test_data) VALUES ('$TEST_DATA') RETURNING id, test_data, created_at;"

echo -e "\n=== Waiting for replication to sync (3 seconds) ==="
sleep 3

echo -e "\n=== Checking data on slave1 ==="
docker-compose -f docker-compose-replication.yml exec db-slave1 psql -U postgres -d social_network -c "
SELECT * FROM replication_test ORDER BY id DESC LIMIT 5;"

echo -e "\n=== Checking data on slave2 ==="
docker-compose -f docker-compose-replication.yml exec db-slave2 psql -U postgres -d social_network -c "
SELECT * FROM replication_test ORDER BY id DESC LIMIT 5;"

echo -e "\n=== Testing read-only status on slaves ==="
echo "Attempting to insert on slave1 (should fail):"
docker-compose -f docker-compose-replication.yml exec db-slave1 psql -U postgres -d social_network -c "
INSERT INTO replication_test (test_data) VALUES ('This should fail on slave');" || echo "Insert failed as expected (slave is read-only)"

echo -e "\nAttempting to insert on slave2 (should fail):"
docker-compose -f docker-compose-replication.yml exec db-slave2 psql -U postgres -d social_network -c "
INSERT INTO replication_test (test_data) VALUES ('This should fail on slave');" || echo "Insert failed as expected (slave is read-only)"
