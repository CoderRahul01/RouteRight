"""Tests for FastAPI server endpoints in mock mode."""

import pytest
from fastapi.testclient import TestClient

from routeright.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_serve_ui(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "RouteRight" in res.text


def test_chat_endpoint(client):
    res = client.post("/api/chat", json={"message": "What is the capital of France?"})
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert "route" in data
    assert "confidence" in data
    assert "decision_latency_ms" in data
    assert "model_used" in data
    assert "question" in data
    assert data["question"] == "What is the capital of France?"


def test_savings_endpoint(client):
    res = client.get("/api/savings")
    assert res.status_code == 200
    data = res.json()
    assert "total_decisions" in data
    assert "actual_cost_usd" in data


def test_history_endpoint(client):
    res = client.get("/api/history")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_reset_endpoint(client):
    res = client.post("/api/reset")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_auth_register_and_stats(client):
    # Register test user
    res = client.post("/api/auth/register", json={"name": "Alice Tester", "email": "alice@test.org"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "user" in data
    assert data["user"]["name"] == "Alice Tester"
    assert "visitor_number" in data["user"]

    # Check stats endpoint
    res_stats = client.get("/api/stats/users")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "total_visitors" in stats
    assert stats["total_visitors"] >= 1


def test_status_endpoint(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["free_mode"] is True
