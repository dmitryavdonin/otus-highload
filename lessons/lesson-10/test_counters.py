#!/usr/bin/env python3
"""
E2E test for Counter Service and SAGA pattern
"""
import requests
import time
import json
import sys
from datetime import datetime, timedelta

# Configuration
API_BASE = "http://localhost:8000"
DIALOG_BASE = "http://localhost:8002"
COUNTER_BASE = "http://localhost:8003"

def check_service_health():
    """Check if all services are healthy"""
    services = [
        (f"{API_BASE}/health", "monolith"),
        (f"{DIALOG_BASE}/health", "dialog"),
        (f"{COUNTER_BASE}/health", "counter")
    ]
    
    print("Checking services health...")
    for url, name in services:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"[{name}] OK")
            else:
                print(f"[{name}] FAIL: HTTP {resp.status_code}")
                return False
        except Exception as e:
            print(f"[{name}] FAIL: {e}")
            return False
    return True

def register_user(first_name, second_name, password="test123"):
    """Register a new user"""
    data = {
        "first_name": first_name,
        "second_name": second_name,
        "birthdate": "1990-01-01T00:00:00",
        "biography": "test user",
        "city": "Test City",
        "password": password
    }
    
    print(f"Registering user: {data}")
    try:
        resp = requests.post(f"{API_BASE}/user/register", json=data, timeout=10)
        print(f"Registration response: {resp.status_code} - {resp.text[:200]}")
        
        if resp.status_code != 200:
            print(f"Registration failed: {resp.status_code} - {resp.text}")
            return None
        
        result = resp.json()
        user_id = result.get("id")  # API returns "id", not "user_id"
        print(f"Registration successful: user_id={user_id}")
        return user_id
    except Exception as e:
        print(f"Registration exception: {e}")
        return None

def login_user(user_id, password="test123"):
    """Login user and get token"""
    data = {
        "id": user_id,
        "password": password
    }
    
    resp = requests.post(f"{API_BASE}/user/login", json=data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code} - {resp.text}")
        return None
    
    result = resp.json()
    return result.get("token")

def send_message(from_token, to_user_id, text):
    """Send a message from user to another user"""
    headers = {
        "Authorization": f"Bearer {from_token}",
        "Content-Type": "application/json"
    }
    data = {"text": text}
    
    resp = requests.post(f"{API_BASE}/dialog/{to_user_id}/send", json=data, headers=headers)
    if resp.status_code != 200:
        print(f"Send message failed: {resp.status_code} - {resp.text}")
        return None
    
    result = resp.json()
    return result.get("message_id")

def get_counters(user_id):
    """Get counters for user"""
    resp = requests.get(f"{COUNTER_BASE}/api/v1/counters/{user_id}")
    if resp.status_code != 200:
        print(f"Get counters failed: {resp.status_code} - {resp.text}")
        return None
    
    return resp.json()

def mark_read(user_id, peer_user_id, delta):
    """Mark messages as read"""
    data = {
        "user_id": user_id,
        "peer_user_id": peer_user_id,
        "delta": delta
    }
    
    resp = requests.post(f"{COUNTER_BASE}/api/v1/counters/mark_read", json=data)
    if resp.status_code != 200:
        print(f"Mark read failed: {resp.status_code} - {resp.text}")
        return None
    
    result = resp.json()
    return result.get("applied", False)

def wait_for_counter_change(user_id, expected_total, expected_peer_count, peer_id, timeout=10):
    """Wait for counter to reach expected values"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        counters = get_counters(user_id)
        if counters:
            total = counters.get("total_unread", 0)
            by_peer = counters.get("by_peer", {})
            peer_count = by_peer.get(peer_id, 0)
            
            print(f"Counters: total={total} by_peer[{peer_id}]={peer_count}")
            
            if total == expected_total and peer_count == expected_peer_count:
                return True
        
        time.sleep(1)
    
    return False

def test_basic_scenario():
    """Test basic counter scenario: send 1 message, read 1 message"""
    print("=== Test Basic Scenario ===")
    
    # Register users
    print("Registering users...")
    user1_id = register_user("User1", "Test")
    user2_id = register_user("User2", "Test")
    
    if not user1_id or not user2_id:
        print("FAIL: User registration failed")
        return False
    
    print(f"U1={user1_id}")
    print(f"U2={user2_id}")
    
    # Login user1
    print("Login user1...")
    token1 = login_user(user1_id)
    if not token1:
        print("FAIL: Login failed")
        return False
    
    print(f"TOKEN1 length={len(token1)}")
    
    # Send message U1 -> U2
    print("Send message U1 -> U2...")
    message_id = send_message(token1, user2_id, "Test message")
    if not message_id:
        print("FAIL: Send message failed")
        return False
    
    print(f"MessageId={message_id}")
    
    # Wait for counter increment
    print("Waiting for counter increment...")
    if not wait_for_counter_change(user2_id, 1, 1, user1_id):
        print("FAIL: Counter not incremented")
        return False
    
    # Mark as read
    print("Mark as read (delta=1)...")
    applied = mark_read(user2_id, user1_id, 1)
    if not applied:
        print("FAIL: Mark read failed")
        return False
    
    print(f"MarkRead applied={applied}")
    
    # Wait for counter decrement
    print("Waiting for counter decrement...")
    if not wait_for_counter_change(user2_id, 0, 0, user1_id):
        print("FAIL: Counter not decremented")
        return False
    
    print("SUCCESS: Basic scenario passed")
    return True

def test_multi_message_scenario():
    """Test multiple messages scenario with partial reads"""
    print("\n=== Test Multi-Message Scenario ===")
    
    # Register users
    print("Registering users...")
    user1_id = register_user("Multi1", "Test")
    user2_id = register_user("Multi2", "Test")
    
    if not user1_id or not user2_id:
        print("FAIL: User registration failed")
        return False
    
    print(f"U1={user1_id}")
    print(f"U2={user2_id}")
    
    # Login user1
    token1 = login_user(user1_id)
    if not token1:
        print("FAIL: Login failed")
        return False
    
    # Send 10 messages
    print("Sending 10 messages U1 -> U2...")
    for i in range(1, 11):
        message_id = send_message(token1, user2_id, f"Important message #{i}")
        if not message_id:
            print(f"FAIL: Send message {i} failed")
            return False
        print(f"Message {i} ID={message_id}")
    
    # Wait for counters to update (should be 10)
    print("Waiting for counters to update to 10...")
    time.sleep(3)  # Give time for async processing
    
    if not wait_for_counter_change(user2_id, 10, 10, user1_id):
        print("FAIL: Counters not updated to 10")
        return False
    
    print("✅ All 10 messages registered in counters!")
    
    # Read only 3 messages
    print("\nStep 1: Mark 3 messages as read...")
    applied = mark_read(user2_id, user1_id, 3)
    if not applied:
        print("FAIL: Mark read failed")
        return False
    
    # Should have 7 unread remaining
    print("Waiting for counter to show 7 remaining...")
    if not wait_for_counter_change(user2_id, 7, 7, user1_id):
        print("FAIL: Counter should show 7 remaining")
        return False
    
    print("✅ After reading 3: 7 messages remain unread")
    
    # Read 4 more messages
    print("\nStep 2: Mark 4 more messages as read...")
    applied = mark_read(user2_id, user1_id, 4)
    if not applied:
        print("FAIL: Mark read failed")
        return False
    
    # Should have 3 unread remaining
    print("Waiting for counter to show 3 remaining...")
    if not wait_for_counter_change(user2_id, 3, 3, user1_id):
        print("FAIL: Counter should show 3 remaining")
        return False
    
    print("✅ After reading 7 total: 3 messages remain unread")
    
    # Read all remaining messages
    print("\nStep 3: Mark all remaining 3 messages as read...")
    applied = mark_read(user2_id, user1_id, 3)
    if not applied:
        print("FAIL: Mark read failed")
        return False
    
    # Should have 0 unread remaining
    print("Waiting for counter to show 0 remaining...")
    if not wait_for_counter_change(user2_id, 0, 0, user1_id):
        print("FAIL: Counter should show 0 remaining")
        return False
    
    print("✅ After reading all 10: 0 messages remain unread")
    
    print("SUCCESS: Multi-message scenario passed - demonstrated partial reads!")
    return True

def test_multiple_senders_scenario():
    """Test counters with multiple senders"""
    print("\n=== Test Multiple Senders Scenario ===")
    
    # Register 3 users
    print("Registering 3 users...")
    user1_id = register_user("Sender1", "Test")
    user2_id = register_user("Sender2", "Test")
    user3_id = register_user("Receiver", "Test")
    
    if not user1_id or not user2_id or not user3_id:
        print("FAIL: User registration failed")
        return False
    
    print(f"Sender1={user1_id}")
    print(f"Sender2={user2_id}")
    print(f"Receiver={user3_id}")
    
    # Login both senders
    token1 = login_user(user1_id)
    token2 = login_user(user2_id)
    if not token1 or not token2:
        print("FAIL: Login failed")
        return False
    
    # Send messages from both senders to receiver
    print("\nSender1 sends 5 messages to Receiver...")
    for i in range(1, 6):
        message_id = send_message(token1, user3_id, f"From Sender1: Message {i}")
        if not message_id:
            print(f"FAIL: Send message {i} from Sender1 failed")
            return False
        print(f"Sender1 -> Message {i} ID={message_id}")
    
    print("\nSender2 sends 3 messages to Receiver...")
    for i in range(1, 4):
        message_id = send_message(token2, user3_id, f"From Sender2: Message {i}")
        if not message_id:
            print(f"FAIL: Send message {i} from Sender2 failed")
            return False
        print(f"Sender2 -> Message {i} ID={message_id}")
    
    # Wait for counters to update
    print("\nWaiting for counters to update...")
    time.sleep(4)
    
    # Check total should be 8, and by_peer breakdown
    counters = get_counters(user3_id)
    if not counters:
        print("FAIL: Could not get counters")
        return False
    
    total = counters.get("total_unread", 0)
    by_peer = counters.get("by_peer", {})
    from_sender1 = by_peer.get(user1_id, 0)
    from_sender2 = by_peer.get(user2_id, 0)
    
    print(f"📊 Final counters for Receiver:")
    print(f"   Total unread: {total}")
    print(f"   From Sender1: {from_sender1}")
    print(f"   From Sender2: {from_sender2}")
    
    if total != 8:
        print(f"FAIL: Expected total=8, got {total}")
        return False
    
    if from_sender1 != 5:
        print(f"FAIL: Expected 5 from Sender1, got {from_sender1}")
        return False
    
    if from_sender2 != 3:
        print(f"FAIL: Expected 3 from Sender2, got {from_sender2}")
        return False
    
    print("✅ All counters are correct!")
    
    # Now read some messages from Sender1 only
    print(f"\nReceiver reads 2 messages from Sender1...")
    applied = mark_read(user3_id, user1_id, 2)
    if not applied:
        print("FAIL: Mark read failed")
        return False
    
    time.sleep(2)
    
    # Check updated counters
    counters = get_counters(user3_id)
    if not counters:
        print("FAIL: Could not get counters")
        return False
    
    total = counters.get("total_unread", 0)
    by_peer = counters.get("by_peer", {})
    from_sender1 = by_peer.get(user1_id, 0)
    from_sender2 = by_peer.get(user2_id, 0)
    
    print(f"📊 After reading 2 from Sender1:")
    print(f"   Total unread: {total}")
    print(f"   From Sender1: {from_sender1}")
    print(f"   From Sender2: {from_sender2}")
    
    if total != 6:  # 8 - 2 = 6
        print(f"FAIL: Expected total=6, got {total}")
        return False
    
    if from_sender1 != 3:  # 5 - 2 = 3
        print(f"FAIL: Expected 3 from Sender1, got {from_sender1}")
        return False
    
    if from_sender2 != 3:  # unchanged
        print(f"FAIL: Expected 3 from Sender2, got {from_sender2}")
        return False
    
    print("✅ Partial read from specific sender works correctly!")
    print("SUCCESS: Multiple senders scenario passed - demonstrated by_peer counters!")
    return True

def main():
    """Main test function"""
    print("Starting Counter Service E2E Tests")
    
    # Check services health
    if not check_service_health():
        print("FAIL: Services not healthy")
        sys.exit(1)
    
    # Run tests
    tests_passed = 0
    total_tests = 3
    
    if test_basic_scenario():
        tests_passed += 1
    
    if test_multi_message_scenario():
        tests_passed += 1
    
    if test_multiple_senders_scenario():
        tests_passed += 1
    
    # Summary
    print(f"\n=== Test Summary ===")
    print(f"Passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("ALL TESTS PASSED! 🎉")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED! ❌")
        sys.exit(1)

if __name__ == "__main__":
    main()
