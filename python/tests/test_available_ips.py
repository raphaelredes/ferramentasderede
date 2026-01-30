import sys
import os
import logging

# Add python directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.network.tools import NetworkTools
import ipaddress

def test_discovery():
    tools = NetworkTools()
    # Use a small range for testing
    cidr = "127.0.0.1/32" 
    # Or better, a small local range if possible, but 127.0.0.1/32 will just find localhost and say 0 available if it finds it, or 1 if not.
    # Let's try a fake range that won't respond to avoid network traffic, or just mock check_host_status.
    
    # Actually, let's just run it on localhost.
    print(f"Scanning {cidr}...")
    
    for result in tools.discover_hosts(ipaddress.ip_network(cidr), "test_task"):
        print(result)
        if result.get("status") == "completed":
            print("\n--- Completion Data ---")
            print(f"Available Count: {result.get('available_count')}")
            print(f"Available Ranges: {result.get('available_ranges')}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_discovery()
