import sys
import os
import logging

# Add python directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.host_manager import HostManager
from src.core.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_add_hosts_direct():
    hm = HostManager()
    
    # Clean up test hosts if they exist
    test_ips = ["192.168.1.201", "192.168.1.202", "192.168.1.203"]
    for ip in test_ips:
        db.delete_host(ip)
    
    hm.load_hosts()
    
    # 1. Add first host (No Name)
    host1 = {
        "name": None,
        "ip": "192.168.1.201",
        "monitoring": True
    }
    print("Adding Host 1 (No Name)...")
    success, msg = hm.add_host(host1)
    print(f"Host 1 Result: {success} - {msg}")
    
    # 2. Add second host (No Name)
    host2 = {
        "name": "",
        "ip": "192.168.1.202",
        "monitoring": True
    }
    print("Adding Host 2 (Empty Name)...")
    success, msg = hm.add_host(host2)
    print(f"Host 2 Result: {success} - {msg}")
    
    # 3. Add third host (With Name)
    host3 = {
        "name": "Test Host 3",
        "ip": "192.168.1.203",
        "monitoring": True
    }
    print("Adding Host 3 (With Name)...")
    success, msg = hm.add_host(host3)
    print(f"Host 3 Result: {success} - {msg}")

    # 4. Add duplicate IP (Should fail)
    print("Adding Duplicate IP...")
    success, msg = hm.add_host(host1)
    print(f"Duplicate IP Result: {success} - {msg}")

if __name__ == "__main__":
    test_add_hosts_direct()
