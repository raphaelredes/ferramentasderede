import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add python directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from api.server import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_get_hosts():
    response = client.get("/hosts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_monitor_stats():
    response = client.get("/network/monitor")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)

def test_security_status():
    response = client.get("/security/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_unlocked" in data
    assert "has_vault" in data
