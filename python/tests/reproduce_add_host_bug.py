import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_add_hosts():
    # 1. Add first host (No Name)
    host1 = {
        "address": "192.168.1.201",
        "monitoring": True
    }
    print("Adding Host 1 (No Name)...")
    try:
        res = requests.post(f"{BASE_URL}/hosts", json=host1)
        print(f"Host 1 Response: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Failed to add Host 1: {e}")

    time.sleep(1)

    # 2. Add second host (No Name)
    host2 = {
        "address": "192.168.1.202",
        "monitoring": True
    }
    print("Adding Host 2 (No Name)...")
    try:
        res = requests.post(f"{BASE_URL}/hosts", json=host2)
        print(f"Host 2 Response: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Failed to add Host 2: {e}")

    time.sleep(1)

    # 3. Add third host (No Name)
    host3 = {
        "address": "192.168.1.203",
        "monitoring": True
    }
    print("Adding Host 3 (No Name)...")
    try:
        res = requests.post(f"{BASE_URL}/hosts", json=host3)
        print(f"Host 3 Response: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Failed to add Host 3: {e}")

if __name__ == "__main__":
    test_add_hosts()
