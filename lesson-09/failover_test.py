#!/usr/bin/env python3

import requests
import json
import time
import sys
import subprocess
import random
from datetime import datetime
from typing import Optional, Dict, Any

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class FailoverTester:
    def __init__(self):
        self.base_url = "http://localhost"
        self.session = requests.Session()
        self.session.timeout = 10
        
    def log(self, message: str):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{Colors.BLUE}[{timestamp}]{Colors.NC} {message}")
        
    def success(self, message: str):
        """Success message"""
        print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")
        
    def error(self, message: str):
        """Error message"""
        print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")
        
    def warning(self, message: str):
        """Warning message"""
        print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")

    def get_auth_token(self) -> Optional[str]:
        """
        Register a test user and get authentication token
        Returns clean token without any ANSI escape codes
        """
        timestamp = int(time.time())
        test_user = {
            "first_name": f"TestUser{timestamp}",
            "second_name": "Failover",
            "birthdate": "2000-01-01T00:00:00",
            "biography": "Failover test user",
            "city": "TestCity",
            "password": "test123"
        }
        
        # Register user with retry logic
        for attempt in range(1, 6):
            try:
                reg_response = self.session.post(
                    f"{self.base_url}/user/register",
                    json=test_user,
                    headers={"Content-Type": "application/json"}
                )
                
                if reg_response.status_code == 200:
                    user_data = reg_response.json()
                    user_id = user_data.get('id')
                    
                    if user_id:
                        # Login with the user ID
                        login_data = {"id": user_id, "password": "test123"}
                        
                        for auth_attempt in range(1, 6):
                            try:
                                auth_response = self.session.post(
                                    f"{self.base_url}/user/login",
                                    json=login_data,
                                    headers={"Content-Type": "application/json"}
                                )
                                
                                if auth_response.status_code == 200:
                                    auth_data = auth_response.json()
                                    token = auth_data.get('token')
                                    if token:
                                        # Validate token format
                                        if len(token) > 10 and token.isalnum():
                                            return token
                                        else:
                                            self.warning(f"Token format looks suspicious: '{token[:20]}...'")
                                            return None
                                elif auth_response.status_code == 500 and auth_attempt < 5:
                                    time.sleep(auth_attempt * 2)
                                    continue
                                else:
                                    break
                                    
                            except requests.RequestException:
                                if auth_attempt < 5:
                                    time.sleep(auth_attempt * 2)
                                    continue
                                break
                        
                elif reg_response.status_code == 500 and attempt < 5:
                    time.sleep(attempt * 2)
                    continue
                else:
                    break
                    
            except requests.RequestException:
                if attempt < 5:
                    time.sleep(attempt * 2)
                    continue
                break
                
        return None

    def test_api_read(self, token: str) -> bool:
        """Test API read operation (user search)"""
        try:
            response = self.session.get(
                f"{self.base_url}/user/search",
                params={"first_name": "Test", "second_name": "User"},
                headers={"Authorization": f"Bearer {token}"}
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def test_api_write(self, token: str) -> bool:
        """Test API write operation (post creation)"""
        timestamp = int(time.time())
        post_data = {"text": f"Test post from failover test {timestamp}"}
        
        try:
            response = self.session.post(
                f"{self.base_url}/post/create",
                json=post_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                self.warning(f"Authentication failed (401) - token may be expired or invalid")
                return False
            else:
                self.error(f"POST request failed with status {response.status_code}")
                self.error(f"Response: {response.text}")
                self.error(f"Post data: {json.dumps(post_data)}")
                return False
                
        except requests.RequestException as e:
            self.error(f"Request exception: {e}")
            return False

    def test_api_with_auth(self, operation: str, retry_on_auth_fail: bool = True) -> bool:
        """Test API operation with authentication"""
        for attempt in range(3):  # Try up to 3 times
            token = self.get_auth_token()
            if not token:
                self.error("Failed to get authentication token")
                return False
                
            if operation == "read":
                success = self.test_api_read(token)
            elif operation == "write":
                success = self.test_api_write(token)
            else:
                self.error(f"Unknown operation: {operation}")
                return False
                
            if success or not retry_on_auth_fail:
                return success
                
            # If failed and we have more attempts, wait and try again
            if attempt < 2:
                self.warning(f"Operation {operation} failed (attempt {attempt + 1}/3), retrying with new token...")
                time.sleep(2)
                
        return False

    def check_service_health(self, port: int) -> bool:
        """Check if application service is healthy"""
        try:
            response = self.session.get(f"http://localhost:{port}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def check_nginx_health(self) -> bool:
        """Check nginx load balancer health"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_haproxy_stats(self) -> Dict[str, str]:
        """Get HAProxy statistics"""
        try:
            response = self.session.get("http://localhost:8404/stats;csv", timeout=5)
            if response.status_code == 200:
                stats = {}
                for line in response.text.strip().split('\n'):
                    if 'postgres-' in line:
                        parts = line.split(',')
                        if len(parts) > 17:
                            name = parts[1]
                            status = "UP" if parts[17] == "UP" else "DOWN"
                            stats[name] = status
                return stats
        except requests.RequestException:
            pass
        return {}

    def show_haproxy_stats(self):
        """Display HAProxy statistics"""
        stats = self.get_haproxy_stats()
        print("================================")
        for name, status in stats.items():
            icon = "✅" if status == "UP" else "❌"
            print(f"  {icon} {name}: {status}")
        print()

    def check_app_availability(self):
        """Check availability of all application instances"""
        print("================================")
        for port in [9001, 9002, 9003]:
            if self.check_service_health(port):
                self.success(f"app{port-9000}: available (HTTP 200)")
            else:
                self.error(f"app{port-9000}: unavailable (HTTP 000)")
                
        if self.check_nginx_health():
            self.success("nginx load balancer: working (HTTP 200)")
        else:
            self.error("nginx load balancer: problems (HTTP 000)")

    def kill_container(self, container_name: str):
        """Kill a Docker container"""
        try:
            result = subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                return True
            else:
                self.warning(f"Container {container_name} already stopped")
                return False
        except subprocess.SubprocessError:
            return False

    def check_docker_services(self):
        """Check Docker services status"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "table {{.Names}}\\t{{.Status}}", "--filter", "name=lesson-09"],
                capture_output=True, text=True, check=True
            )
            print(result.stdout)
        except subprocess.SubprocessError:
            self.error("Failed to check Docker services")

    def test_combined_failure(self):
        """Test combined failure scenario - kill postgres-slave2 and app3"""
        self.log("🔥 COMBINED FAILURE TEST")
        print("================================")
        
        # Show initial state
        self.log("Initial state:")
        self.log("HAProxy statistics:")
        self.show_haproxy_stats()
        
        self.log("Application availability check:")
        self.check_app_availability()
        
        # Kill services simultaneously
        self.log("Killing postgres-slave2 and app3 simultaneously...")
        self.kill_container("lesson-09-postgres-slave2-1")
        self.kill_container("lesson-09-app3-1")
        
        # Wait for system to detect failures
        time.sleep(5)
        
        # Show state after failures
        self.log("State after failures:")
        self.log("HAProxy statistics:")
        self.show_haproxy_stats()
        
        self.log("Application availability check:")
        self.check_app_availability()
        
        # Test system functionality
        self.log("Testing system functionality...")
        
        # Test write operation
        self.log("Testing write through API...")
        if self.test_api_with_auth("write"):
            self.success("Write through API works (post creation successful)")
            write_success = True
        else:
            self.error("Write through API failed!")
            write_success = False
            
        # Test read operation
        self.log("Testing read through API after combined failure...")
        if self.test_api_with_auth("read"):
            self.success("Read through API works after combined failure")
            read_success = True
        else:
            self.error("Read through API failed!")
            read_success = False
            
        # Final result
        if write_success and read_success:
            self.success("✅ Combined test passed successfully")
            return True
        else:
            self.warning("⚠️ Combined test completed with warnings")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 failover_test.py <test_type>")
        print("Available tests: combined")
        sys.exit(1)
        
    test_type = sys.argv[1]
    tester = FailoverTester()
    
    # Check Docker services first
    tester.log("Checking service status...")
    tester.check_docker_services()
    
    if test_type == "combined":
        success = tester.test_combined_failure()
        sys.exit(0 if success else 1)
    else:
        tester.error(f"Unknown test type: {test_type}")
        sys.exit(1)

if __name__ == "__main__":
    main() 