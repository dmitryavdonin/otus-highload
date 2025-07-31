import time
import uuid
import os
import subprocess

# Function to execute SQL on a specific database
def execute_sql(container, sql):
    cmd = f"docker-compose -f docker-compose-replication.yml exec {container} psql -U postgres -d social_network -c \"{sql}\""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout

# Generate a unique test ID
test_id = str(uuid.uuid4())
timestamp = int(time.time())

print(f"=== Testing PostgreSQL Replication with test_id: {test_id} ===")

# Insert data on master
print("\n=== Inserting test data on master ===")
insert_sql = f"INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password) VALUES ('{test_id}', 'Test{timestamp}', 'User', '2000-01-01', 'Testing replication', 'Test City', 'password123') RETURNING id, first_name, second_name;"
master_result = execute_sql("db-master", insert_sql)
print(master_result)

# Wait for replication to sync
print("\n=== Waiting for replication to sync (3 seconds) ===")
time.sleep(3)

# Check data on slave1
print("\n=== Checking data on slave1 ===")
slave1_result = execute_sql("db-slave1", f"SELECT id, first_name, second_name FROM users WHERE id = '{test_id}';")
print(slave1_result)

# Check data on slave2
print("\n=== Checking data on slave2 ===")
slave2_result = execute_sql("db-slave2", f"SELECT id, first_name, second_name FROM users WHERE id = '{test_id}';")
print(slave2_result)

# Test read-only status on slaves
print("\n=== Testing read-only status on slaves ===")
print("Attempting to insert on slave1 (should fail):")
slave1_insert = execute_sql("db-slave1", f"INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password) VALUES ('{uuid.uuid4()}', 'TestFail', 'User', '2000-01-01', 'This should fail', 'Test City', 'password123');")
print(slave1_insert)

print("\nAttempting to insert on slave2 (should fail):")
slave2_insert = execute_sql("db-slave2", f"INSERT INTO users (id, first_name, second_name, birthdate, biography, city, password) VALUES ('{uuid.uuid4()}', 'TestFail', 'User', '2000-01-01', 'This should fail', 'Test City', 'password123');")
print(slave2_insert)

# Verify replication is working by checking replication status
print("\n=== Checking replication status ===")
replication_status = execute_sql("db-master", "SELECT * FROM pg_stat_replication;")
print(replication_status)

print("\n=== Test completed ===")
