#!/usr/bin/env python
import subprocess
import sys
import os
import time

def run_parallel_imports(total_users=1000000, num_processes=4):
    """
    Run multiple import processes in parallel
    """
    users_per_process = total_users // num_processes
    
    print(f"Starting {num_processes} parallel import processes, {users_per_process} users each")
    
    processes = []
    
    for i in range(num_processes):
        cmd = [sys.executable, "generate_million_users.py", str(users_per_process)]
        print(f"Starting process {i+1}: {' '.join(cmd)}")
        
        # Start process
        process = subprocess.Popen(cmd)
        processes.append(process)
    
    # Wait for all processes to complete
    for i, process in enumerate(processes):
        print(f"Waiting for process {i+1} to complete...")
        process.wait()
        print(f"Process {i+1} completed with return code {process.returncode}")

if __name__ == "__main__":
    # Get total number of users and number of processes from command line arguments
    total_users = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
    num_processes = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    
    # Run parallel imports
    run_parallel_imports(total_users, num_processes)
