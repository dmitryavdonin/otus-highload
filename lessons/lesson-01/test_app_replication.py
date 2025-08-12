import requests
import json
import time
import uuid
from datetime import datetime, timedelta

# Base URL for the API
base_url = "http://localhost:9000"

# Function to register a user (writes to master)
def register_user():
    user_data = {
        "first_name": f"Test{int(time.time())}",
        "second_name": "User",
        "birthdate": "2000-01-01",
        "biography": "Testing replication setup",
        "city": "Test City",
        "password": "password123"
    }
    
    response = requests.post(f"{base_url}/user/register", json=user_data)
    if response.status_code == 200:
        print(f"✅ Successfully registered user on master: {response.json()}")
        return response.json()["id"]
    else:
        print(f"❌ Failed to register user: {response.status_code} - {response.text}")
        return None

# Function to login (reads from slaves)
def login(user_id, password):
    login_data = {
        "id": user_id,
        "password": "password123"
    }
    
    response = requests.post(f"{base_url}/user/login", json=login_data)
    if response.status_code == 200:
        print(f"✅ Successfully logged in: {response.json()}")
        return response.json()["token"]
    else:
        print(f"❌ Failed to login: {response.status_code} - {response.text}")
        return None

# Function to get a user (reads from slaves)
def get_user(user_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # Make multiple requests to see if they're load balanced between slaves
    for i in range(5):
        response = requests.get(f"{base_url}/user/get/{user_id}", headers=headers)
        if response.status_code == 200:
            print(f"✅ Request {i+1}: Successfully retrieved user from slave: {response.json()}")
        else:
            print(f"❌ Request {i+1}: Failed to retrieve user: {response.status_code} - {response.text}")
        time.sleep(0.5)  # Small delay between requests

# Main test
print("Testing application connections to master and slaves...")
user_id = register_user()

if user_id:
    print("\nWaiting 2 seconds for replication to sync...")
    time.sleep(2)
    
    token = login(user_id, "password123")
    
    if token:
        print("\nTesting read requests (should be load balanced between slaves):")
        get_user(user_id, token)
        
        print("\nTest completed!")
    else:
        print("Test failed: Could not login.")
else:
    print("Test failed: Could not register user on master.")
