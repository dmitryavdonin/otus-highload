import requests
import json
import time

# Base URL for the API
base_url = "http://localhost:9000"

# Function to create a user (writes to master)
def create_user():
    user_data = {
        "first_name": f"Test{int(time.time())}",
        "last_name": "User",
        "email": f"test{int(time.time())}@example.com",
        "password": "password123",
        "interests": ["testing", "replication"]
    }
    
    response = requests.post(f"{base_url}/users", json=user_data)
    if response.status_code == 200:
        print(f"✅ Successfully created user on master: {response.json()}")
        return response.json()["id"]
    else:
        print(f"❌ Failed to create user: {response.status_code} - {response.text}")
        return None

# Function to get a user (reads from slaves)
def get_user(user_id):
    # Make multiple requests to see if they're load balanced between slaves
    for i in range(5):
        response = requests.get(f"{base_url}/users/{user_id}")
        if response.status_code == 200:
            print(f"✅ Request {i+1}: Successfully retrieved user from slave: {response.json()}")
        else:
            print(f"❌ Request {i+1}: Failed to retrieve user: {response.status_code} - {response.text}")
        time.sleep(0.5)  # Small delay between requests

# Main test
print("Testing application connections to master and slaves...")
user_id = create_user()

if user_id:
    print("\nWaiting 2 seconds for replication to sync...")
    time.sleep(2)
    
    print("\nTesting read requests (should be load balanced between slaves):")
    get_user(user_id)
    
    print("\nTest completed!")
else:
    print("Test failed: Could not create user on master.")
