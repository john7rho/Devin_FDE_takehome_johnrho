"""Smoke tests for the FastAPI surface using TestClient."""
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_metrics_empty(temp_db):
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    assert r.json()["total_sessions"] == 0


def test_sessions_empty(temp_db):
    r = client.get("/api/v1/sessions")
    assert r.status_code == 200
    assert r.json() == []


def test_unknown_session_404(temp_db):
    r = client.get("/api/v1/sessions/does-not-exist")
    assert r.status_code == 404


def test_seed_endpoint_removed(temp_db):
    r = client.post("/api/v1/seed")
    assert r.status_code == 404
